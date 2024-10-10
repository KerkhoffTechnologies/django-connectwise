# -*- coding: utf-8 -*-
VERSION = (1, 6, 6, 'final')

# pragma: no cover
if VERSION[-1] != "final":
    __version__ = '.'.join(map(str, VERSION))
else:
    # pragma: no cover
    __version__ = '.'.join(map(str, VERSION[:-1]))

default_app_config = 'djconnectwise.apps.DjangoConnectwiseConfig'
