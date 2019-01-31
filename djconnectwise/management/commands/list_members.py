from django.core.management.base import BaseCommand
from djconnectwise.models import Member


class Command(BaseCommand):
    help = 'List active, full-license ConnectWise members.'

    def handle(self, *args, **options):
        for member in Member.objects.filter(inactive=False, license_class='F'):
            self.stdout.write(
                '{:15} {:20} {:43}'.format(
                    member.identifier,
                    member.__str__(),
                    member.office_email,
                )
            )
