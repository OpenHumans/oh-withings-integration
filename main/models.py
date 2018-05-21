from django.db import models
from open_humans.models import OpenHumansMember
import arrow
from datetime import timedelta

class NokiaHealthMember(models.Model):
    """
    Store OAuth2 data for Open Humans member.
    A User account is created for this Open Humans member.
    """
    user = models.OneToOneField(OpenHumansMember, related_name="nokia_member", on_delete=models.CASCADE)
    userid = models.CharField(max_length=16, primary_key=True, unique=True)
    deviceid = models.CharField(max_length=16)
    oauth_token = models.CharField(max_length=256)
    oauth_token_secret = models.CharField(max_length=256)
    last_updated = models.DateTimeField(
                            default=(arrow.now() - timedelta(days=7)).format())
    last_submitted = models.DateTimeField(
                            default=(arrow.now() - timedelta(days=7)).format())

