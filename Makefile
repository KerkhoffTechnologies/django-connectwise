SHELL=/bin/bash

.PHONY: clean
clean:
	rm -rf build/ dist/ django_connectwise.egg-info/

install: clean
	python setup.py install

upload:
	twine upload dist/*
