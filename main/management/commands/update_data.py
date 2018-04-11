from django.core.management.base import BaseCommand
from main.models import NokiaHealthMember
from main.views import fetch_nokia_data


class Command(BaseCommand):
    help = 'Updates data for all members'

    def handle(self, *args, **options):
        users = NokiaHealthMember.objects.all()
        for user in users:
            fetch_nokia_data(user, user.access_token)
