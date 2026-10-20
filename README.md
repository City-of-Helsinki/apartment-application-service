# apartment-application-service
Apartment application service

## Development with Docker

1. Copy the contents of .env.example to .env and modify it if needed.

2. Run docker-compose up

The project is now running at [localhost:8081](http://localhost:8081)

## Development without Docker

Prerequisites:

* PostgreSQL 12
* Python 3.12
* Pip 26.01

### Installing Python requirements

* Run `pip install -r requirements.txt`
* Run `pip install -r requirements-dev.txt` (development requirements)

### Database

To setup a database compatible with default database settings:

Create user and database

    sudo -u postgres createuser -P -R -S apartment-application  # use password `apartment-application`
    sudo -u postgres createdb -O apartment-application apartment-application

Allow user to create test database

    sudo -u postgres psql -c 'ALTER USER "apartment-application" CREATEDB;'

### Database encryption

Some model fields are encrypted using `pgcrypto`, which requires a PGP keypair.
For instructions on how to generate the keys, see the
[pgcrypto documentation](https://postgresql.org/docs/12/pgcrypto.html#id-1.11.7.34.7.19):

Use the PostgreSQL preferred key type ("DSA and Elgamal") and *at least* 2048 bits
as the key size.

To convert the multi-line PEM key into a single line (for `.env`), you can use this snippet:

    cat your-key-file | awk '{print}' ORS='\\n'

For local development, you can use the example keys in `.env.example`.
**Do not use these example keys in production!**

### Daily running

* Create `.env` file: `touch .env`
* Set the `DEBUG` environment variable to `1`.
* Run `python manage.py migrate`
* Run `python manage.py runserver 0:8081`

The project is now running at [localhost:8081](http://localhost:8081)


## Makefile targets

If you have the `make` command available, you can use the following commands to run certain common tasks:

* `make check` - Run all checks (linting, Django checks, tests)
* `make lint` - Run linters (flake8, black, isort)
* `make test` - Run tests
* `make fix` - Run code formmitng fixes (isort, black)
* `make requirements` - Update all requirements `*.txt` files from their
  corresponding `*.in` files
* `make deploy` - Run the deployment tasks (migrate, compilemessages,
  collectstatic)


## E2E tests

The E2E stack runs `apartment-application-service` (Django) and `drupal-asuntotuotanto` (Drupal) together in isolated Docker containers. It does not require Stonehenge or any other host services.

### Prerequisites

- Docker with Compose v2
- Both repos cloned as siblings: `drupal-asuntotuotanto/` and `apartment-application-service/` in the same parent directory
- `att-sales-ui/` cloned as a sibling as well, for the sales UI tests. Set `SALES_UI_PATH` in `.env.e2e` to use a clone elsewhere.

### First-time setup

1. Copy the env template and fill in the dump paths:

    ```bash
    cp env.e2e.example .env.e2e
    ```

2. Edit `.env.e2e`:
   - Set `DRUPAL_DUMP_PATH` to the SQL dump file from `drupal-asuntotuotanto` (relative to this directory, e.g. `../drupal-asuntotuotanto/dump-2026-04-23.sql`)
   - Set `DJANGO_DUMP_PATH` to a Django JSON fixture (relative path, e.g. `../django-dump-XXXXXXXXXX.json`). Leave unset to start with an empty Django DB.
   - Set `PUBLIC_PGP_KEY` / `PRIVATE_PGP_KEY` — see below.
   - Set `E2E_DJANGO_DB_PASSWORD` to any URL-safe value. It only takes effect when the Postgres volume is first created, so run the teardown command below with `-v` after changing it.
   - Keep `E2E_DRUPAL_DB_PASSWORD=drupal`; it must match the default user built into the `druidfi/mariadb` image.


### Running the stack

```bash
# Start all services and keep them running
docker compose -f compose.e2e.yaml --env-file .env.e2e up --build

# Or use the helper script (tears down on finish):
./run-e2e.sh

# Keep the stack running after tests finish (useful for debugging):
./run-e2e.sh --keep
```

Services exposed on the host (bound to `127.0.0.1` only):

| Service | URL |
|---|---|
| Drupal | http://localhost:18080 |
| Django API | http://localhost:18081/api_docs/ |
| Drupal MariaDB | localhost:13306 |
| Django Postgres | localhost:15434 |
| Mock OIDC provider | http://localhost:18083/e2e/.well-known/openid-configuration |
| Sales UI (CRA dev server) | http://localhost:13000 |
| E2E seeder | http://localhost:18084/health |

### Authenticating against the Django sales API

The `mock-oidc` service ([navikt/mock-oauth2-server](https://github.com/navikt/mock-oauth2-server)) issues signed JWTs that Django accepts as Bearer tokens (`OIDC_ISSUER=http://mock-oidc:8080/e2e`, `OIDC_AUDIENCE=apartment-application-service`). Tokens are obtained with the `client_credentials` grant from `/e2e/token` (any client id/secret); the `scope` parameter selects the claims defined in `mock-oidc-config.json`:

| Scope | Result |
|---|---|
| `e2e-salesperson` | salesperson user, accepted (200) |
| `e2e-customer` | authenticated user without the salesperson role (403) |
| `e2e-wrong-audience` | rejected (401) |

On startup `django_e2e_seed_salesperson.py` adds the user whose UUID is `E2E_SALESPERSON_SUB` (defaults to the `e2e-salesperson` token's `sub`) to the `django_salesperson` group.

The mock sets each token's `iss` from the Host header used to reach it, so only tokens fetched as `mock-oidc:8080` are trusted. From the host, add the header:

```bash
curl -s -H "Host: mock-oidc:8080" -d grant_type=client_credentials \
  -d client_id=e2e -d client_secret=e2e -d scope=e2e-salesperson \
  http://localhost:18083/e2e/token
```

`mock-oidc` is an nginx proxy in front of the actual mock server (`mock-oidc-server`). It passes requests through unchanged except for one case, described in `mock-oidc-proxy.conf`: a token request with a `Bearer` Authorization header (the sales UI's API token request) has that header replaced with dummy client credentials, because the mock does not accept the request otherwise.

### Sales UI login

The `sales-ui` service runs att-sales-ui against the mock provider. Logging in uses the authorization code flow with PKCE: the UI redirects to the mock's login page, where the username entered becomes the user token's `sub`. The UI then requests an API token for `apartment-application-service` (grant type `E2E_API_GRANT_TYPE`, default `client_credentials`), which the mock issues from the `audience` mapping in `mock-oidc-config.json`.

That API token always has the seeded salesperson as its `sub`, whatever username was used to log in. Any logged-in UI user therefore acts as the seeded salesperson against the Django API, so the UI tests cannot cover per-user API permissions.

The UI loads at http://localhost:13000 from the host, but logging in works only from inside the compose network (the test-runner container), since the UI redirects to and calls `mock-oidc` and `django-app` by their in-network hostnames. Chromium is started with `--unsafely-treat-insecure-origin-as-secure` for the UI and mock origins (see `tests-e2e/playwright.config.ts`) because PKCE needs `crypto.subtle`, which is available only in secure contexts.

### Baseline content

`e2e/fixtures/baseline.json` is committed Drupal content that the tests can rely on, independent of what the SQL dump contains. It lists projects, each with its apartments:

- `key`: stable identifier for test code (`^[a-z0-9-]+$`, unique; apartment keys are unique across the file).
- `uuid`: the Drupal node UUID, which is also Django's `project_uuid` / `apartment_uuid`. Use canonical lowercase UUIDs starting with `e2e0` (e.g. `e2e00003-0000-4000-8000-000000000301`) so they never clash with real content.
- `ownership_type`: a term name of the Drupal `ownership_type` vocabulary (`HASO`, `Hitas`, `Puolihitas`).
- Projects: `housing_company` (starts with `E2E `), `street_address`, optional `postal_code` and `city`. Apartments: `apartment_number` (unique within the project), optional `apartment_structure`, `living_area`, `floor`.

On every drupal-app start, `drupal-e2e-deploy.sh` runs `drush php:script /e2e/fixtures/drupal/load_baseline.php` after the config import. The loader finds each node by UUID and creates or updates it in place, so restarts never duplicate content. Nodes are published, projects get state of sale "for sale" and their `field_apartments` lists exactly the baseline apartments in file order. The loader then reindexes the apartments in the search_api indexes (`apartment`, `apartment_listing`), or leaves them queued when the Elasticsearch server is unavailable. It prints a summary line (`[e2e-baseline] Loaded ...`) to the drupal-app logs. Invalid input or a failed save stops drupal-app before nginx starts.

`e2e/scenarios/baseline.py` validates the file (tested by `e2e/scenarios/tests/test_baseline.py`) and `tests-e2e/tests/baseline/baseline-content.spec.ts` checks that Django's sales API serves it. To add content, add entries to `baseline.json`, run the pytest file, then restart drupal-app (and django-app, which caches its Drupal token) to load it. Removing an entry from the file does not delete the node from Drupal.

### Scenarios and the seeder

Specs that need specific Django data seed it per test through the `e2e-seeder` service (`e2e/seeder/server.py`, http://localhost:18084 from the host, `http://e2e-seeder:8090` in the compose network). It runs django-app's image with `e2e/` mounted, waits until django-app has applied the migrations, and handles one request at a time:

- `GET /health` lists the registered scenarios.
- `POST /scenarios/<name>` with a JSON object of params resets and seeds the scenario and returns a JSON manifest of what it created (400 for invalid params, 404 for an unknown scenario).

Specs use the `seedScenario` fixture from `tests-e2e/tests/utils.ts`:

```ts
test('...', async ({ page, seedScenario }) => {
  const seed = await seedScenario<Manifest>('haso_queue', { variant: 'on_time' });
  // seed.apartment_uuid, seed.new_customer.last_name, ...
});
```

The fixture adds a `namespace` derived from the worker index and test id (`^[a-z0-9-]{1,40}$`) unless one is passed. Scenarios embed it in the names of the rows they create and reset only their own namespace's rows, so parallel tests do not see each other's customers. Scenarios that share an apartment do reset each other's reservations on it, so parallel specs should seed different apartments.

To add a scenario, create a module in `e2e/scenarios/` with a function decorated with `@scenario("<name>")` (`e2e/scenarios/registry.py`) that takes the params dict and returns a JSON-serializable manifest, import the module in `e2e/scenarios/__init__.py`, and add tests next to `e2e/scenarios/tests/test_haso_queue.py`. Validate params before any database access and raise `ScenarioParamsError` for invalid ones. Resolve apartments and projects through the baseline (`load_baseline().apartment(key)`) and refuse, with `RuntimeError` before writing anything, to touch apartments whose uuid does not start with `e2e0`, so a scenario can never modify non-baseline content. Restart `e2e-seeder` to load changes.

`haso_queue` (used by `tests/sales-ui/haso-reservation-queue.spec.ts`, which reproduces a HASO queue ordering bug) resets a HASO baseline apartment (`on_time`: `haso-a1`, `late`: `haso-a2`, or `apartment_key`), leaves one lottery event on it, and creates an existing customer (right of residence 500, non-late reservation at queue position 1) and a new customer (right of residence 100, no reservation).

### Teardown

```bash
docker compose -p att-e2e down -v
```

The `-v` flag removes the DB volumes so the next run starts with a clean database. Omit it to keep the data.

### What happens on startup

- **Drupal**: the SQL dump is imported into MariaDB on first start (empty volume only). `drush updatedb` and `drush cim` run on every start, followed by provisioning of the OAuth consumer Django uses to fetch project data from Drupal (`ASU_REST_OAUTH_CLIENT_ID` / `ASU_REST_OAUTH_CLIENT_SECRET`) and loading the baseline content (see above).
- **Django**: migrations run, then if `DJANGO_DUMP_PATH` is set the fixture is flushed into the DB (duplicates in the dump are deduplicated automatically by `django_dedup_fixture.py`). The E2E salesperson user is then seeded by `django_e2e_seed_salesperson.py`.
- **Seeder**: `e2e-seeder` polls `manage.py migrate --check` until django-app has applied the migrations, then starts serving.

### Adding tests

Place Playwright test files in `tests-e2e/`. The `test-runner` service in `compose.e2e.yaml` mounts that directory and exits with the test process's exit code. Replace the placeholder `command` with your actual Playwright invocation.

## Tests

Run the test suite with `make test` or `pytest`.

Integration tests are skipped by default (they require external services like Drupal).
To run them, pass the `--integration-tests` flag:

```
pytest --integration-tests
```

Mark tests as integration tests with the `@integration_test` decorator:

```python
from conftest import integration_test

@integration_test
def test_something_against_real_api():
    ...
```


## Keeping Python requirements up to date

This project uses [`pip-tools`](https://github.com/jazzband/pip-tools)
to manage the Python requirements.  It works with two kind of files:
`*.in` and `*.txt`.  The `*.in` files are the source files, which list
the directly required packages and their version constraints.  The
`*.txt` files are generated from the `*.in` files and they list the
exact versions of the packages that are installed.

1. `pip-tools` is installed from `requirements-dev.txt`:

    * `pip install -r requirements-dev.txt`

2. Add new packages to `requirements.in` or `requirements-dev.in`

3. Update `.txt` file for the changed requirements file:

    * `pip-compile requirements.in`
    * `pip-compile requirements-dev.in`
    * There is also a Makefile target for updating all requirement
      files: `make requirements`

4. If you want to update dependencies to their newest versions, run:

    * `pip-compile --upgrade requirements.in`

5. To install Python requirements run:

    * `pip-sync requirements*.txt`


## Code Formatting and Linting

This project uses
[`black`](https://github.com/psf/black),
[`flake8`](https://gitlab.com/pycqa/flake8) and
[`isort`](https://github.com/PyCQA/isort)
for code formatting and quality checking. Project follows the basic
black config, without any modifications.

Basic `black` commands:

* To let `black` do its magic: `black .`
* To see which files `black` would change: `black --check .`

There is also `make lint` and `make fix` commands for code style
checking and fixing.

For Django, this project mostly follows the styleguide defined in
[Django-Styleguide](https://github.com/HackSoftware/Django-Styleguide).


## SAP Integration
To be able to send installments to SAP, the following settings need to be set:
```
SAP_SFTP_SEND_USERNAME
SAP_SFTP_SEND_PASSWORD
SAP_SFTP_SEND_HOST
SAP_SFTP_SEND_PORT
```
Also,
```
python manage.py send_installments_to_sap
```
needs to be run periodically.

For fetching payments from SAP, the following settings need to be set:
```
SAP_SFTP_FETCH_USERNAME
SAP_SFTP_FETCH_PASSWORD
SAP_SFTP_FETCH_HOST
SAP_SFTP_FETCH_PORT
```
Also,
```
python manage.py fetch_payments_from_sap
```
needs to be run periodically.

You may also use variables named `SAP_SFTP_USERNAME`,
`SAP_SFTP_PASSWORD`, `SAP_SFTP_HOST` and `SAP_SFTP_PORT` to set default
values for the corresponding send/fetch settings.

### Testing / exceptional situations

There are also two other management commands, which should not be needed for normal usage, but can be useful for testing purposes and exceptional situations:

* Generating an XML file of given installments
```
python manage.py create_sap_xml [reference numbers]
```
* Sending an XML file to the SAP SFTP server
```
python manage.py send_sap_xml <filename>
```

## Cronjobs

There are few commands that are needed to be run periodically to get full functionality of some features. The easiest way to do this should be using cron. 

* to get SAP invoices actually sent to the SFTP server
   ```
   python manage.py send_pending_installments_to_sap
   ```
   once a day during night at some point.

* to get reservation states updated based on expired offers
   ```
   python manage.py update_reservations_based_on_offer_expiration
   ```
   once a day as close to midnight as possible, but must be after it.
