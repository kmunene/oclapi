from django.conf.urls.defaults import patterns, url
from sources.views import SourceListView, SourceUpdateDetailView

__author__ = 'misternando'

urlpatterns = patterns('',
    url(r'^$', SourceListView.as_view(), name='source-list'),
    url(r'^(?P<source>[a-zA-Z0-9\-]+)/$', SourceUpdateDetailView.as_view(), name='source-detail'),
)
