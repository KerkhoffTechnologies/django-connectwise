from django.utils.translation import ugettext_lazy as _
from . import _callback


class Command(_callback.Command):
    help = str(_('Deletes the callback from the target connectwise system.'))
    ACTION = 'delete'
