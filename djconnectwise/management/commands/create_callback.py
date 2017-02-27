from django.utils.translation import ugettext_lazy as _
from . import _callback


class Command(_callback.Command):
    help = _('Registers the callback with the target connectwise system.')
    ACTION = 'create'
