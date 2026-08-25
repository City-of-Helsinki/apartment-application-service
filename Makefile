check: lint check-django check-migrations check-requirements check-sanitizerconfig test

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

check-sanitizerconfig:
	./manage.py check_sanitizerconfig

# Directory for anonymized dumps (gitignored sanitized_*.sql files).
SANITIZED_DUMP_DIR ?= .

create-sanitized-dump:
	@mkdir -p "$(SANITIZED_DUMP_DIR)"
	@# Delete the 5th-oldest dump and older (keep the four newest).
	@old=$$(ls -1t "$(SANITIZED_DUMP_DIR)"/sanitized_*.sql 2>/dev/null | tail -n +5); \
	if [ -n "$$old" ]; then \
		echo "Removing old dumps:"; \
		echo "$$old"; \
		echo "$$old" | xargs rm -f --; \
	fi
	@outfile="$(SANITIZED_DUMP_DIR)/sanitized_$$(date +%Y%m%d%H%M%S).sql"; \
	./manage.py create_sanitized_dump > "$$outfile"; \
	echo "Created $$outfile"

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
