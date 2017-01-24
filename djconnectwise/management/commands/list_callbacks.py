from django.core.management.base import BaseCommand
from djconnectwise.callback import CallBackHandler


class Command(BaseCommand):
    help = 'Lists existing callbacks on target connectwise system.'

    def handle(self, *args, **options):
        handler = CallBackHandler() 

        print('Callback List')
        print('-----------------------------------------')      
        for c in handler.list_callbacks():
            print('{0} - {1}'.format(c['id'], c['url']))