from django.contrib import admin
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from djangotoolbox.fields import ListField
from rest_framework.authtoken.models import Token
from oclapi.models import BaseResourceModel
from sources.models import Source

USER_OBJECT_TYPE = 'User'
ORG_OBJECT_TYPE = 'Organization'


class UserProfile(BaseResourceModel):
    user = models.OneToOneField(User)
    full_name = models.TextField(null=True, blank=True)
    company = models.TextField(null=True, blank=True)
    location = models.TextField(null=True, blank=True)
    preferred_locale = models.CharField(max_length=20, null=True, blank=True)
    organizations = ListField()
    sources = ListField()

    def __unicode__(self):
        return self.name

    @property
    def name(self):
        return self.full_name or "%s %s" % (self.user.first_name, self.user.last_name)

    @classmethod
    def resource_type(cls):
        return USER_OBJECT_TYPE

    @property
    def username(self):
        return self.mnemonic or self.user.username

    @property
    def email(self):
        return self.user.email

    @property
    def orgs(self):
        return len(self.organizations)

    @property
    def public_sources(self):
        return Source.objects.filter(parent_id=self.id).count()

    @staticmethod
    def get_url_kwarg():
        return 'user'

    @classmethod
    @receiver(post_save, sender=User)
    def create_auth_token(sender, instance=None, created=False, **kwargs):
        if created:
            Token.objects.create(user=instance)


admin.site.register(UserProfile)