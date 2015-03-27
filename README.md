This is a package that allows indexing of django models using
elasticsearch. It requires django, elasticsearch-py and a local instance of
elasticsearch.


Features:
Several predefined SearchFields for elasticsearch mappings
SearchMixin and Search inner class allows defining model-based indexing
Management commands (create_index and update_index)
Django signal receivers for updating data

Usage:
You must define ELASTICSEARCH_CONNECTIONS in your django settings.

For example:
ELASTICSEARCH_CONNECTIONS = {
    'default': {
        'HOSTS': ['http://localhost:9200',],
        'INDEX_NAME': {{ INDEX_NAME }}
    }
}

using SearchMixin and Search inner-class:

class Foo(models.Model, SearchMixin):
    name = models.Charield(‘name’,max_length=255)

    class Search(SearchMixin.Search):
        attribute_fields = (‘name’)

See comments in models.py for more documentation on use
