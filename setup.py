#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

LONG_DESCRIPTION = open('README.md').read()

VERSION = (1, 13, 8)

project_version = '.'.join(map(str, VERSION))

setup(
    name="django-connectwise",
    version=project_version,
    description='Django app for working with ConnectWise. '
                'Defines models (tickets, members, companies, etc.) '
                'and callbacks.',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    keywords='django connectwise rest api python',
    packages=find_packages(),
    author='Kerkhoff Technologies Inc.',
    author_email='matt@kerkhofftech.ca',
    url="https://github.com/KerkhoffTechnologies/django-connectwise",
    include_package_data=True,
    license='MIT',
    install_requires=[
        'requests',
        'django',
        'python-dateutil',
        'django-model-utils',
        'django-braces',
        'django-extensions',
        'retrying',
        'Pillow',
    ],
    test_suite='runtests.suite',
    tests_require=[
        'responses',
        'model-mommy',
        'django-coverage',
        'names'
    ],
    # Django likes to inspect apps for /migrations directories, and can't if
    # package is installed as a egg. zip_safe=False disables installation as
    # an egg.
    zip_safe=False,
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Development Status :: 3 - Alpha',
    ],
)
