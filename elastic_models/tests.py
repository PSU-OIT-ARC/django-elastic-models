from django.db import models

from oro import tests
from .models import SearchMixin
from .receivers import suspended_updates, get_search_models


class TestModel(SearchMixin, models.Model):
    name = models.CharField(max_length=256)
    modified_on = models.DateTimeField(auto_now=True)

    class Search(SearchMixin.Search):
        attribute_fields = ['name']

class SearchPostSaveTestCase(tests.TestCase):
    def test_post_save(self):
        self.assertIn(TestModel, get_search_models())

        self.assertEqual(TestModel.search.count(), 0)

        tm = TestModel(name="Test1")
        tm.save()

        self.refresh_index()
        self.assertEqual(TestModel.search.count(), 1)

    def test_suspended_updates(self):
        self.assertEqual(TestModel.search.count(), 0)

        with suspended_updates():
            tm = TestModel(name="Test2")
            tm.save()

            self.refresh_index()
            self.assertEqual(TestModel.search.count(), 0)

        self.refresh_index()
        self.assertEqual(TestModel.search.count(), 1)

