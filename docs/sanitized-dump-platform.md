# ASU-1886: Scheduled sanitized dumps — platform setup

What the platform side (OpenShift / `asuntotuotanto-pipelines`) needs to
provide so that anonymized copies of production data are created regularly
**inside the production cluster**, and personal data never leaves it.

The application code is done: both apps have a dump command that reads the
live database and writes an anonymized SQL file. Live rows are never changed.

## 1. Scheduled jobs (production namespace)

Two jobs, run back to back (Django first, then Drupal), e.g. weekly at night.
Run them close together: the dumps are linked by user UUIDs, so users created
between the two dumps won't match after restore.

| | Django (apartment-application-service) | Drupal (drupal-asuntotuotanto) |
|---|---|---|
| Image | the deployed production image | the deployed production image |
| Env / secrets | same as the app pod (DB credentials etc.) | same as the app pod |
| Command | `make create-sanitized-dump SANITIZED_DUMP_DIR=/dumps/django` | `drush asu:sql:sanitized-dump --directory=/dumps/drupal` |
| Output | `sanitized_YYYYMMDDHHMMSS.sql`, the 4 newest kept | same |
| DB access needed | read only (`pg_dump`) | read only (single transaction) |

Both commands write to a `.tmp` file and rename it only on success. Old dumps
are deleted only after a successful dump, so a failed run leaves the previous
dumps in place. Both exit non-zero on failure; alert on that.

If `make` is not available in the Django image, use the equivalent:

```sh
out=/dumps/django/sanitized_$(date +%Y%m%d%H%M%S).sql
./manage.py create_sanitized_dump > "$out.tmp" && [ -s "$out.tmp" ] && mv "$out.tmp" "$out" \
  || { rm -f "$out.tmp"; exit 1; }
ls -1 /dumps/django/sanitized_*.sql | sort -r | tail -n +5 | xargs -r rm -f
```

The Drupal command refuses to run (non-zero exit) if a custom table gains a
column that has no anonymization rule. That's intended: it fails instead of
leaking. Report it to the developers.

### To verify first

- **Postgres version.** The Django image ships `pg_dump` 13 (`postgresql` from
  UBI 9). `pg_dump` refuses to dump a newer server. If production Postgres is
  newer than 13, the image needs a matching client.
- **Size and duration.** Local dev data dumps in a few seconds (Django 7 MB,
  Drupal 58 MB). Production is larger; size the volume and job timeout from a
  first manual run.

## 2. Storage and access

- A persistent volume (or object storage) in the production namespace, mounted
  at `/dumps` in both jobs. Each app keeps its own 4 newest files.
- The dumps contain no personal data, but they are production-shaped business
  data, and they keep some identifiers on purpose: user OIDC subjects
  (`users_user.uuid`) and right-of-residence numbers. Give read access to the
  project's developers only.
- Developers need a way to download the newest pair (Django + Drupal from the
  same run), e.g. `oc rsync` / `oc cp` from a helper pod, or a pre-signed link
  from object storage.

## 3. Loading into the test server

After copying the newest pair into the test environment:

1. Import the Django dump into the test Postgres (`psql -f`; use a `psql` at
   least as new as the `pg_dump` that wrote it) and the Drupal dump into the
   test MariaDB.
2. In the test backend pod:
   `./manage.py drupal_restore_credentials_sql --i-know-this-is-a-restored-dump > fix.sql`
3. In the test Drupal pod: `drush sql:query --file=fix.sql`, then `drush cr`.
4. If the deployed code is newer than the dump: `./manage.py migrate` and
   `drush deploy`.

Step 2–3 re-links Drupal users to their backend profiles for the test
environment's `HASHIDS_SALT`; without it no customer can reach the backend.
**Never run step 3 against production**: it sets every Drupal user's backend
password to `localdev`.

All restored users' passwords are `localdev`. For the Drupal dump this can be
changed by setting `ASU_SANITIZED_DUMP_PASSWORD_HASH` (a Drupal password hash)
in the Drupal dump job, e.g. from a secret. Customer SAML logins will not map
to restored Drupal users: their SAML hashes are replaced and `authmap` data is
left out.

## 4. Check the setup

`docs/sanitized-dump-restore-check.md` runs the whole cycle locally with
throwaway containers, including a check that Drupal users reach their backend
profiles after the fix. Run it after changing anonymization rules.
