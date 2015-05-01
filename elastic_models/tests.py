from elasticsearch import Elasticsearch
from elasticsearch_dsl import Q as SQ

from django.db import models
from django import test
from django.conf import settings
from django.test.runner import DiscoverRunner

from .indexes import Index, index_registry
from .fields import StringField, NestedObjectListField
from .receivers import suspended_updates



class SearchRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super(SearchRunner, self).setup_test_environment(**kwargs)
        self._old_search_indexes = {}
        for name, connection in list(settings.ELASTICSEARCH_CONNECTIONS.items()):
            self._old_search_indexes[name] = connection['INDEX_NAME']
            connection['INDEX_NAME'] = connection['INDEX_NAME'] + "_test"

        for index in index_registry.values():
            index.put_mapping()

    def teardown_test_environment(self, **kwargs):
        super(SearchRunner, self).teardown_test_environment(**kwargs)
        for name, connection in list(settings.ELASTICSEARCH_CONNECTIONS.items()):
            connection['INDEX_NAME'] = self._old_search_indexes[name]



class SearchTestMixin(test.SimpleTestCase):
    def _pre_setup(self):
        super(SearchTestMixin, self)._pre_setup()

        for name, connection in list(settings.ELASTICSEARCH_CONNECTIONS.items()):
            es = Elasticsearch(connection['HOSTS'])
            es.delete_by_query(index=connection['INDEX_NAME'], body={'query': {'match_all': {}}})

        self.refresh_index()

    def refresh_index(self):
        for name, connection in list(settings.ELASTICSEARCH_CONNECTIONS.items()):
            es = Elasticsearch(connection['HOSTS'])
            es.indices.refresh(index=connection['INDEX_NAME'])



class SearchTestCase(SearchTestMixin, test.TestCase):
    pass



class TestIndex(Index):
    declared_name = StringField('name')
    shadowable_name = StringField('name')
    tags = NestedObjectListField('tags', attribute_fields=('tag', 'count'))
    
    class Meta():
        attribute_fields = ('name',)
        dependencies = {'elastic_models.Tag': 'tags'}

class TestDerivedIndex(TestIndex):
    derived_declared_name = StringField('name')
    shadowable_name = None
    
    class Meta():
        pass



class Tag(models.Model):
    tag = models.CharField(max_length=256)
    count = models.IntegerField()
    tm = models.ForeignKey('elastic_models.TestModel', related_name="tags")
    modified_on = models.DateTimeField(auto_now=True, auto_now_add=True)
    

class TestModel(models.Model):
    name = models.CharField(max_length=256)
    modified_on = models.DateTimeField(auto_now=True, auto_now_add=True)
    
    search = TestIndex()
    derived_search = TestDerivedIndex()



class IndexTestCase(SearchTestCase):
    def test_field_inheritance(self):
        self.assertIn('name', TestModel.derived_search.fields.keys())
        self.assertIn('declared_name', TestModel.derived_search.fields.keys())
        self.assertIn('derived_declared_name', TestModel.derived_search.fields.keys())
        self.assertNotIn('shadowable_name', TestModel.derived_search.fields.keys())
    

class IndexBehaviorTestCase(SearchTestCase):
    def setUp(self):
        super(IndexBehaviorTestCase, self).setUp()
        
        self.tm1 = TestModel(name="Test1")
        self.tm1.save()
        self.tm2 = TestModel(name="Test2")
        self.tm2.save()
        
        self.tm1.tags.create(tag="Tag1", count=10)
        self.tm1.tags.create(tag="Tag2", count=20)
        
        self.refresh_index()
    
    def test_attribute_field(self):
        hits = TestModel.search.query("match", name="Test1").execute().hits
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].pk, self.tm1.pk)
    
    def test_declared_field(self):
        hits = TestModel.search.query("match", declared_name="Test1").execute().hits
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].pk, self.tm1.pk)
    
    def test_nested_field(self):
        nested_query = SQ("match", tags__tag = "Tag1")
        nested_query += SQ("match", tags__count=10)
        search = TestModel.search.query("nested", path="tags", query=nested_query)
        hits = search.execute().hits
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].pk, self.tm1.pk)
        
        nested_query = SQ("match", tags__tag = "Tag1")
        nested_query += SQ("match", tags__count=20)
        hits = TestModel.search.query("nested", path="tags", query=nested_query).execute().hits
        self.assertFalse(hits)

class SearchPostSaveTestCase(SearchTestCase):
    def test_post_save(self):
        self.assertIn(TestModel.search, index_registry.values())

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
