This is a package that allows indexing of django models using
elasticsearch. It requires django, elasticsearch-py and a local instance of
elasticsearch.


Features:
-------
Several predefined SearchFields for elasticsearch mappings

SearchMixin and Search inner class allows defining model-based indexing

Management commands (create_index and update_index)

Django signal receivers for updating data

Usage:

Add `‘elastic_models’` to `INSTALLED_APPS`

You must define `ELASTICSEARCH_CONNECTIONS` in your django settings.

For example:

    ELASTICSEARCH_CONNECTIONS = {
        'default': {
            'HOSTS': ['http://localhost:9200',],
            'INDEX_NAME': 'my_index'
        }
    }

In order to create a test search index you must add to your settings.py:

    TEST_RUNNER = 'elastic_models.tests.SearchRunner'

and base your test case on `elastic_models.tests.SearchTestCase`.


using `SearchMixin` and `Search` inner-class:

    class Foo(models.Model, SearchMixin):
        name = models.Charield(‘name’,max_length=255)
    
        class Search(SearchMixin.Search):
            attribute_fields = (‘name’)

>>>>>>> Rename test case and test runner
See comments in models.py for more documentation on use

Tests:
-----
To run the test suite for Python 2 and Python 3:

    make test

It is assumed you have a `virtualenv` in your path, and Elasticsearch running
on localhost:9200
