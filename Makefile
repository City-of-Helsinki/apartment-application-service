requirements: requirements.txt requirements-dev.txt requirements-prod.txt

requirements.txt: requirements.in
	pip-compile --resolver=backtracking $<

requirements-dev.txt: requirements-dev.in requirements.txt
	pip-compile --resolver=backtracking $<

requirements-prod.txt: requirements-prod.in requirements.txt
	pip-compile --resolver=backtracking $<
