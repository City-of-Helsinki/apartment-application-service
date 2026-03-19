# AGENTS.md

You are an expert Python+Django fullstack developer. All the code you write must be highly maintainable, secure and scalable. 

## Project
- Python 3.12
- Django Rest Framework
- PostgreSQL 12

## Helpful commands
- `make lint` checks the code for lint errors
- `make fix-code-style` uses the Black-formatter to fix style errors
- `docker exec -it apartment-application-backend bash -c "pytest"` runs the entire test suite

## General directives
- dont tell the user to edit files, edit the files yourself. That is your job as an agent.
- always write tests
- you must use TDD, tests should always be written before other code changes
- write both negative and positive test cases
- run the tests after finished with writing code to assure they pass
- this repository is public, the code should NEVER contain any secrets such as API keys
- load settings from environment variables in settings.py
- code should be modular and unit testable
- always write docstrings for functions/methods


## Building
- build the container with `docker-compose -f docker-compose.yml build` or in development mode: `docker-compose -f docker-compose-dev.yml build` 

## Tests
- external APIs should always be mocked to avoid side effects

## Code style
- follow the PEP8 style conventions for Python code
- maximum line length is 88 characters
- use double quotes for all strings
- use f-strings for formatted strings

## Django best practices
- try to use built-in Django features whenever possible
- use `django.contrib.auth.get_user_model` to acquire the currently used User model
- when creating a new model, subclass it from `apartment_application_service.models.TimestampedModel`
- when adding new strings, make them translatable by using `django.utils.translation.gettext_lazy` (which will always be imported with as "_" to save on line length)

### Django ORM
- avoid the n+1 problem 
- use `.select_related()` and `.prefetch()`-methods to optimize database access

### Views
- use the Django Rest Framework (DRF) viewsets for REST api views
- user input should always be validated and sanitized