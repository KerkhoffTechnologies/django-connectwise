SHELL=/bin/bash

.PHONY: clean

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +

clean: clean-build clean-pyc

coverage: ## check code coverage quickly with the default Python
	# Coverage config file at .coveragerc
	coverage run --source djconnectwise runtests.py tests
	coverage report -m

install: clean
	python setup.py install

lint: ## check style with flake8
	# flake8 config file at tox.ini
	flake8 .

test: clean lint
	python setup.py test

sdist: clean
	python setup.py sdist

upload: sdist
    # You must have a ~/.pypirc file with your username and password.
    # You don't need to register new packages first- just upload and
    # everything is taken care of.
	twine upload dist/*.tar.gz
