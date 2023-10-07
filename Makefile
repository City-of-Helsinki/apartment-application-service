check: lint check-django check-migrations check-requirements test

fix: fix-imports fix-code-style

requirements: requirements.txt requirements-dev.txt requirements-prod.txt

deploy:
	./manage.py migrate --noinput
	./manage.py compilemessages
	./manage.py collectstatic --noinput

migrations:
	./manage.py makemigrations

messages:
	./manage.py makemessages --all

lint:
	flake8 .
	black --check --diff .
	isort --check --diff .

check-django:
	./manage.py check

check-migrations:
	./manage.py makemigrations --check --dry-run

check-requirements:
	./check-requirements-files

test:
	pytest

fix-code-style:
	black .

fix-imports:
	isort .

requirements.txt: requirements.in
	pip-compile --strip-extras $<

requirements-dev.txt: requirements-dev.in requirements.txt
	pip-compile --strip-extras $<

requirements-prod.txt: requirements-prod.in requirements.txt
	pip-compile --strip-extras $<
