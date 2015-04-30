This is a package that allows indexing of django models using
elasticsearch. It requires django, elasticsearch-py and a local instance of
elasticsearch.


Features:
---------
Several predefined SearchFields for elasticsearch mappings

Index class allows provides a manager-like interface for model-based indexing.

Management commands (create_index and update_index)

Django signal receivers for updating data

Usage:
------
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


Models are added to the search index by adding an `Index`. In the simplest
cases, when all indexed fields are attributes, and the default behavior is
sufficient, you can just add an instance of `Index`:

    from elastic_models.indexes import Index
    
    class Foo(models.Model):
        name = models.CharField(max_length=255)
        number = models.IntegerField()
    
        search = elastic_models.indexes.Index(attribute_fields=('name', 'number'))

When you want to override the default behavior, create a subclass of `Index`.
For example, if you wanted to index `number` as a string rather than an integer:

    from elastic_models.indexes import Index
    from elastic_models.fields import StringField
    
    class FooIndex(Index):
        number = StringField(attr='number')
        
        class Meta():
            attribute_fields = ['name']
    
    class Foo(models.Model):
        name = models.CharField(max_length=255)
        number = models.IntegerField()

        search = FooIndex()


See comments in models.py for more documentation on use

Tests:
-----
To run the test suite for Python 2 and Python 3:

    make test

It is assumed you have a `virtualenv` in your path, and Elasticsearch running
on localhost:9200
