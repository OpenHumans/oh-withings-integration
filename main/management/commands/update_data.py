from django.core.management.base import BaseCommand
from main.models import NokiaHealthMember
from main.views import fetch_nokia_data
import logging
import schedule
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Updates data for all members'

    def handle(self, *args, **options):
        # users = NokiaHealthMember.objects.all()
        # for user in users:
        #     fetch_nokia_data(user, user.access_token)
        logger.debug('hello')

    # schedule.every().wednesday.at("20:00").do(handle)
    schedule.every(1).minutes.do(handle)


while True:
    schedule.run_pending()
    time.sleep(1)
