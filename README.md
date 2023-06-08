# apartment-application-service
Apartment application service

## Development with Docker

1. Copy the contents of .env.example to .env and modify it if needed.

2. Run docker-compose up

The project is now running at [localhost:8081](http://localhost:8081)

## Development without Docker

Prerequisites:

* PostgreSQL 12
* Python 3.8

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
