# ASU-1886: Sanitized dump restore cycle

Checks that sanitized dumps of the Django (Postgres) and Drupal (MariaDB)
databases can be restored into a fresh environment with a **different
`HASHIDS_SALT`**, and that Drupal users can still reach their backend
profiles after the credential fix.

- **Source:** the local dev stacks, standing in for production. Dumps only read.
- **Target:** throwaway containers on a separate Docker network.
- **Proof:** Drupal's own `BackendApi` + `UserRequest` (login with
  `field_backend_profile` / `field_backend_password`, then
  `GET /v1/profiles/<masked id>/`). It fails before `fix.sql` and works after.

Takes about 10 minutes.

## Prerequisites

| Container | What | Notes |
|---|---|---|
| `apartment-application-backend` | Django dev (this repo, `docker compose up`) | Image `apartment-application-service-django` must be built from the current requirements (`docker compose build django`) |
| `apartment-application-db` | Postgres 12 (source) | |
| `asuntotuotanto-app` | Drupal dev (drupal-asuntotuotanto) | Module `asu_sanitized_dump` enabled (`drush pm:list \| grep asu_sanitized_dump`) |
| `asuntotuotanto-db` | MariaDB 10.6 (source) | |

Both repos checked out on the branch you want to test. Both target app
containers mount the checkouts, so they run whatever is on disk.

Run the commands from the root of this repo, with drupal-asuntotuotanto
checked out next to it:

```bash
A=$(pwd)
D=$(cd ../drupal-asuntotuotanto && pwd)
S=$(mktemp -d)/restore-cycle && mkdir -p "$S"   # working dir for dumps
PW=localdev   # SANITIZED_DUMP_PASSWORD: same value for dumping and restoring
```

## 1. Dump the source databases

```bash
# Django: sanitized pg_dump to stdout
docker exec -e SANITIZED_DUMP_PASSWORD="$PW" apartment-application-backend \
  ./manage.py create_sanitized_dump > "$S/django.sql"

# Drupal: writes sanitized_<timestamp>.sql inside the container, copy it out
docker exec asuntotuotanto-app drush asu:sql:sanitized-dump --directory=/tmp/asu-restore
docker cp "asuntotuotanto-app:$(docker exec asuntotuotanto-app sh -c 'ls /tmp/asu-restore/sanitized_*.sql')" "$S/drupal.sql"
docker exec asuntotuotanto-app rm -rf /tmp/asu-restore
```

## 2. Create the target databases

```bash
docker network create asu-restore
docker run -d --name asu-restore-pg --network asu-restore \
  -e POSTGRES_USER=restore -e POSTGRES_PASSWORD=restore -e POSTGRES_DB=restore postgres:12
docker run -d --name asu-restore-mariadb --network asu-restore \
  -e MYSQL_DATABASE=drupal -e MYSQL_USER=drupal -e MYSQL_PASSWORD=drupal -e MYSQL_ROOT_PASSWORD=drupal \
  druidfi/mariadb:10.6-drupal

until docker exec asu-restore-pg pg_isready -U restore -q \
  && docker exec asu-restore-mariadb mariadb -u drupal -pdrupal -e 'SELECT 1' drupal >/dev/null 2>&1; do sleep 1; done
```

## 3. Restore the dumps

Use `psql` from the backend image, not from `postgres:12`. Recent `pg_dump`
versions write `\restrict` lines that older `psql` clients can't parse.

```bash
docker run --rm -i --network asu-restore --entrypoint psql apartment-application-service-django \
  -v ON_ERROR_STOP=1 -q postgres://restore:restore@asu-restore-pg/restore < "$S/django.sql"

docker exec -i asu-restore-mariadb mariadb -u drupal -pdrupal drupal < "$S/drupal.sql"
```

Optional: compare row counts with the source:

```bash
q="select 'profiles', count(*) from users_profile union all select 'applications', count(*) from application_form_application"
docker exec apartment-application-db psql -U apartment-application -d apartment-application -At -c "$q"
docker exec asu-restore-pg psql -U restore -d restore -At -c "$q"
```

## 4. Start the target apps

**Backend:** this checkout, the restored Postgres, and a salt that differs
from the source. Bypassing the image entrypoint skips its migrate and
superuser steps.

```bash
docker run -d --name asu-restore-django --network asu-restore \
  --env-file "$A/.env" \
  -e DATABASE_URL=postgres://restore:restore@asu-restore-pg/restore \
  -e DATABASE_HOST= -e HASHIDS_SALT=restore-check-salt -e ALLOWED_HOSTS='*' \
  -e SANITIZED_DUMP_PASSWORD="$PW" \
  -v "$A:/app" -w /app --entrypoint python \
  apartment-application-service-django manage.py runserver 0.0.0.0:8081
```

**Drupal:** the Drupal checkout and the restored MariaDB, without Redis.
⚠️ `SIMPLETEST_DB` must be set: the image ships a default pointing at host
`db`, and `settings.php` gives it priority over `DRUPAL_DB_*`.

```bash
docker run -d --name asu-restore-drupal --network asu-restore \
  -v "$D:/app" -w /app \
  -e APP_ENV=dev \
  -e DRUPAL_DB_HOST=asu-restore-mariadb -e DRUPAL_DB_PORT=3306 \
  -e DRUPAL_DB_NAME=drupal -e DRUPAL_DB_USER=drupal -e DRUPAL_DB_PASS=drupal \
  -e SIMPLETEST_DB=mysql://drupal:drupal@asu-restore-mariadb:3306/drupal \
  -e DRUPAL_HASH_SALT=restore-check \
  -e ASU_DJANGO_BACKEND_URL=asu-restore-django:8081 \
  -e DRUPAL_ROUTES=http://localhost \
  --entrypoint sleep ghcr.io/city-of-helsinki/drupal-web:8.4 infinity

docker exec asu-restore-drupal drush status --fields=db-hostname,db-status,bootstrap
# Expect: DB hostname asu-restore-mariadb, Connected, Successful
docker exec asu-restore-drupal drush cr
```

## 5. Baseline check (before the fix)

Save as `$S/check_backend_link.php`:

```php
<?php

/**
 * @file
 * Restore check: can each Drupal user reach their backend profile?
 *
 * Uses Drupal's own BackendApi + UserRequest, which authenticates with
 * field_backend_profile / field_backend_password and then fetches
 * /v1/profiles/<masked id>/. Prints counts only, no personal data.
 */

use Drupal\asu_api\Api\BackendApi\Request\UserRequest;
use Drupal\user\Entity\User;

$uids = \Drupal::database()
  ->query('SELECT entity_id FROM {user__field_backend_profile}')
  ->fetchCol();
$api = \Drupal::service('asu_api.backendapi');
$switcher = \Drupal::service('account_switcher');

$ok = 0;
$id_matches = 0;
$failures = [];
foreach ($uids as $uid) {
  $user = User::load($uid);
  $switcher->switchTo($user);
  try {
    // Same call pattern as asu_user.module and ApplicantWidget.
    $request = new UserRequest($user);
    $request->setSender($user);
    $info = $api->send($request)->getUserInformation();
    $ok++;
    if (($info['id'] ?? NULL) === $user->uuid()) {
      $id_matches++;
    }
  }
  catch (\Throwable $e) {
    $key = get_class($e) . ': ' . substr($e->getMessage(), 0, 80);
    $failures[$key] = ($failures[$key] ?? 0) + 1;
  }
  finally {
    $switcher->switchBack();
  }
}

printf("Drupal users with a backend profile: %d\n", count($uids));
printf("Backend profile fetched OK:          %d\n", $ok);
printf("Returned profile id == users.uuid:   %d\n", $id_matches);
foreach ($failures as $reason => $count) {
  printf("FAILED x%d: %s\n", $count, $reason);
}
```

```bash
docker cp "$S/check_backend_link.php" asu-restore-drupal:/tmp/check_backend_link.php
docker exec asu-restore-drupal drush php:script /tmp/check_backend_link.php
```

Expected: `Backend profile fetched OK: 0`. The `[error]` log lines show
`POST .../v1/token/` → `401 No active account`. The stored credentials are
masked with the source salt.

## 6. Apply the credential fix (the runbook step)

```bash
docker exec asu-restore-django python manage.py drupal_restore_credentials_sql \
  --i-know-this-is-a-restored-dump > "$S/fix.sql"
docker cp "$S/fix.sql" asu-restore-drupal:/tmp/fix.sql
docker exec asu-restore-drupal drush sql:query --file=/tmp/fix.sql
docker exec asu-restore-drupal drush cr
```

`fix.sql` is one transaction: a temporary UUID → masked id table, two
`UPDATE`s and `COMMIT`. **Never apply it to production.** It sets every
Drupal user's backend password to `SANITIZED_DUMP_PASSWORD`. If the target
backend's `SANITIZED_DUMP_PASSWORD` differs from the one used when dumping, the
check in step 7 fails with `401 No active account`.

## 7. Check again (after the fix)

```bash
docker exec asu-restore-drupal drush php:script /tmp/check_backend_link.php
```

Expected: `fetched OK` equals `profile id == users.uuid`, and it equals the
number of Drupal users that are linkable in the source.

If some users still fail, check whether they were already unlinkable in the
source, i.e. no Django profile with the user's UUID, or a profile without a
Django user:

```bash
docker exec asuntotuotanto-db sh -c 'mariadb -N -u drupal -p"$MYSQL_PASSWORD" drupal -e "SELECT u.uuid FROM users u JOIN user__field_backend_profile f ON f.entity_id=u.uid"' | sort > "$S/drupal_uuids"
docker exec apartment-application-db psql -U apartment-application -d apartment-application -At -c "select id from users_profile" | sort > "$S/profiles"
docker exec apartment-application-db psql -U apartment-application -d apartment-application -At -c "select id from users_profile where user_id is null" | sort > "$S/profiles_nouser"
echo "no Django profile: $(comm -23 "$S/drupal_uuids" "$S/profiles" | wc -l)"
echo "profile without user: $(comm -12 "$S/drupal_uuids" "$S/profiles_nouser" | wc -l)"
```

## 8. Optional: confirm personal data was replaced

Compare hashes per row between source and target. The unchanged count
should be 0.

```bash
pq="select id || ' ' || md5(coalesce(email,'')||'|'||coalesce(first_name,'')||'|'||coalesce(last_name,'')||'|'||coalesce(phone_number,'')||'|'||coalesce(street_address,'')) from users_profile where coalesce(email,'')<>''"
docker exec apartment-application-db psql -U apartment-application -d apartment-application -At -c "$pq" | sort > "$S/a"
docker exec asu-restore-pg psql -U restore -d restore -At -c "$pq" | sort > "$S/b"
echo "Django profiles unchanged: $(comm -12 "$S/a" "$S/b" | wc -l) / $(wc -l < "$S/a")"

mq="SELECT CONCAT(id,' ',MD5(CONCAT_WS('|',main_applicant__email,main_applicant__first_name,main_applicant__last_name,main_applicant__personal_id,main_applicant__phone,main_applicant__address))) FROM asu_application WHERE main_applicant__email<>''"
docker exec asuntotuotanto-db sh -c "mariadb -N -u drupal -p\"\$MYSQL_PASSWORD\" drupal -e \"$mq\"" | sort > "$S/a"
docker exec asu-restore-mariadb mariadb -N -u drupal -pdrupal drupal -e "$mq" | sort > "$S/b"
echo "Drupal applications unchanged: $(comm -12 "$S/a" "$S/b" | wc -l) / $(wc -l < "$S/a")"
```

## 9. Clean up

```bash
docker rm -f asu-restore-drupal asu-restore-django asu-restore-pg asu-restore-mariadb
docker network rm asu-restore
rm -rf "$S"
```

## Reference run (2026-10-27, Django `6b33a28`, Drupal `7a7134c5`)

| Check | Result |
|---|---|
| Row counts, source vs target | identical (1,067 profiles, 471 applications; 58 Drupal users, 193 applications) |
| Before fix | 0 / 55 OK, all `401 No active account` |
| After fix | 43 / 55 OK, 43 profile ids match |
| Remaining 12 | Already unlinkable in the source: 11 without a Django profile, 1 profile without a user |
| Unchanged personal data | 0 / 1,049 Django profiles, 0 / 22 Drupal applications, 0 / 57 Drupal users |

## Troubleshooting

- **`drush status` shows `DB hostname: db`:** `SIMPLETEST_DB` isn't
  overridden (step 4).
- **`Typed property ...Request::$sender must not be accessed before
  initialization`:** the request is missing `setSender($user)`.
- **`psql` syntax error near `\restrict`:** restore with the backend image's
  `psql` (step 3).
- **Backend container exits on start:** check `docker logs asu-restore-django`.
  The image must have the branch's requirements (`docker compose build django`).
