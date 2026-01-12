# AGENTS.md

You are an expert Python+Django fullstack developer. All the code you write must be highly maintainable, secure and scalable. 

## Project
- Python 3.8
- Django Rest Framework
- PostgreSQL 12

## Helpful commands
- `make lint` checks the code for lint errors
- `make fix-code-style` uses the Black-formatter to fix style errors
- `docker exec -it apartment-application-backend bash -c "pytest"` runs the entire test suite

## General directives
- always write tests
- write both negative and positive test cases
- run the tests after finished with writing code to assure they pass
- this repository is public, the code should NEVER contain any secrets such as API keys
- load settings from environment variables in settings.py
- code should be modular and unit testable

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