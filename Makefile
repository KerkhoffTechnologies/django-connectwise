SHELL=/bin/bash

.PHONY: clean
clean:
	rm -rf build/ dist/ django_connectwise.egg-info/

install: clean
	python setup.py install

test: clean
	python setup.py test

sdist: test
	python setup.py sdist

upload: sdist
    # You must have a ~/.pypirc file with your username and password.
    # You don't need to register new packages first- just upload and everything is taken care of.
	twine upload dist/*.tar.gz
