django-connectwise
==================

Django app for working with ConnectWise. Defines models (tickets,
members, companies, etc.) and callbacks.

As of January 2017, this project is highly volatile. Expect lots of
changes.

Requirements
------------

-  Python 3.5
-  Django 1.8

Other versions may work; we haven't tried.

Installation
------------

From PyPI:

::

    pip install django-connectwise

From source:

::

    git clone git@github.com:KerkhoffTechnologies/django-connectwise.git
    cd django-connectwise
    python setup.py install

Documentation
-------------

TODO

-  Add to INSTALLED_APPS
-  Available settings
-  Use standard Django model signals to see when this apps objects change
-  Uses easy-thumbnails- can use settings from that project to change
   behaviour http://easy-thumbnails.readthedocs.io/en/stable/ref/settings/. Also
   must add to INSTALLED\_APPS (I think)
-  To use callbacks, must use Sites app- registers with ConnectWise with URL of first Sites instance

License
-------

`MIT <LICENSE>`__

Copyright
---------

© 2017 Kerkhoff Technologies Inc.
