from elasticsearch import Elasticsearch

from django.db import models
from django import test
from django.conf import settings
from django.test.runner import DiscoverRunner

from .models import SearchMixin
from .receivers import suspended_updates, get_search_models

class ServiceTestCaseMixin(test.TestCase):
    def _pre_setup(self):
        super(ServiceTestCaseMixin, self)._pre_setup()

        for name, connection in list(settings.ELASTICSEARCH_CONNECTIONS.items()):
            es = Elasticsearch(connection['HOSTS'])
            es.delete_by_query(index=connection['INDEX_NAME'], body={'query': {'match_all': {}}})

        self.refresh_index()

    def refresh_index(self):
        for name, connection in list(settings.ELASTICSEARCH_CONNECTIONS.items()):
            es = Elasticsearch(connection['HOSTS'])
            es.indices.refresh(index=connection['INDEX_NAME'])


class TestModel(SearchMixin, models.Model):
    name = models.CharField(max_length=256)
    modified_on = models.DateTimeField(auto_now=True, auto_now_add=True)

    class Search(SearchMixin.Search):
        attribute_fields = ['name']

class SearchPostSaveTestCase(ServiceTestCaseMixin, test.TestCase):
    def test_post_save(self):
        self.assertIn(TestModel, get_search_models())

        self.assertEqual(TestModel.search.count(), 0)

        tm = TestModel(name="Test1")
        tm.save()

        self.refresh_index()
        self.assertEqual(TestModel.search.count(), 1)

    def test_suspended_updates(self):
        self.assertEqual(TestModel.search.count(), 0)

        with suspended_updates([TestModel,]):
            tm = TestModel(name="Test2")
            tm.save()
            self.refresh_index()
            self.assertEqual(TestModel.search.count(), 0)

        self.refresh_index()
        self.assertEqual(TestModel.search.count(), 1)

class DefaultSearchRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super(DefaultSearchRunner, self).setup_test_environment(**kwargs)
        self._old_search_indexes = {}
        for name, connection in list(settings.ELASTICSEARCH_CONNECTIONS.items()):
            self._old_search_indexes[name] = connection['INDEX_NAME']
            connection['INDEX_NAME'] = connection['INDEX_NAME'] + "_test"

        for model in get_search_models():
            model._search_meta().put_mapping()

    def teardown_test_environment(self, **kwargs):
        super(DefaultSearchRunner, self).teardown_test_environment(**kwargs)
        for name, connection in list(settings.ELASTICSEARCH_CONNECTIONS.items()):
            connection['INDEX_NAME'] = self._old_search_indexes[name]
