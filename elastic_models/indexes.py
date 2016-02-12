from __future__ import absolute_import
from __future__ import print_function

import logging

from django.conf import settings
from django.db.models.loading import get_model
from django.utils import six

from elasticsearch import Elasticsearch, NotFoundError, exceptions
from elasticsearch.helpers import bulk
import elasticsearch_dsl as dsl

from .fields import FieldMappingMixin, FieldMappingOptions

logger = logging.getLogger(__name__)

index_registry = {}

class IndexOptions(FieldMappingOptions):
    def __init__(self, sources=[]):
        super(IndexOptions, self).__init__(sources=sources)
        
        self.doc_type = self.get_value(sources, 'doc_type', None)
        self.connection = self.get_value(sources, 'connection', 'default')
        self.index_by = self.get_value(sources, 'index_by', 1000)
        self.date_field = self.get_value(sources, 'date_field', 'modified_on')

        # A dictionary whose keys are other models that this model's index
        # depends on, and whose values are query set paramaters for this model
        # to select the instances that depend on an instance of the key model.
        # For example, the index for BlogPost might use inform;:ation from Author,
        # so it would have dependencies = {Author: 'author'}.
        # When an Author is saved, this causes BlogPost's returned by the query
        # BlogPost.objects.filter(author=instance) to be re-indexed.
        self.dependencies = self.get_value(sources, 'dependencies', {})


class Index(FieldMappingMixin):
    _options_class = IndexOptions
    
    def contribute_to_class(self, model, name):
        self.model = model
        self.name = name
        setattr(model, name, self)

        index_registry[(model, name)] = self

    def get_index(self):
        index_name = settings.ELASTICSEARCH_CONNECTIONS[self._meta.connection]['INDEX_NAME']
        return index_name % (self.get_doc_type(),)

    def get_doc_type(self):
        if self._meta.doc_type is not None:
            return self._meta.doc_type
        else:
            return "%s_%s_%s" % (self.model._meta.app_label, self.model._meta.model_name, self.name)

    def get_dependencies(self):
        dependencies = self._meta.dependencies
        for model, query in dependencies.items():
            if isinstance(model, six.string_types):
                (app_name, model_name) = model.split('.')
                model_cls = get_model(app_name, model_name)
                dependencies.pop(model)
                dependencies[model_cls] = query
        return dependencies

    def get_es(self):
        return Elasticsearch(settings.ELASTICSEARCH_CONNECTIONS[self._meta.connection]['HOSTS'])

    def get_search(self):
        s = dsl.Search(using=self.get_es())
        s = s.index(self.get_index())
        s = s.doc_type(self.get_doc_type())
        return s
    
    def get_mapping(self):
        doc_type = self.get_doc_type()
        mapping = dsl.Mapping(doc_type)
        self.add_fields_to_mapping(mapping)
        return mapping
    
    def put_mapping(self):
        mapping = self.get_mapping()
        settings = self.get_settings()
        es = self.get_es()
        
        doc_type = mapping.doc_type
        index = self.get_index()
        
        
        if es.indices.exists(index):
            logger.debug("Removing index '%s'" % (index))
            es.indices.delete(index)
        
        logger.debug("Creating index '%s' and mapping '%s'" % (index, doc_type))
        mapping.save(index, using=es)
        
        if settings:
            try:
                logger.debug("Updating settings for index '%s': %s" % (index, settings))
                es.indices.close(index)
                es.indices.put_settings(settings, index)
            finally:
                es.indices.open(index)
        else:
            logger.debug("Not settings to update for index '%s'" % (index))
    
    def index_instance(self, instance):
        self.get_es().index(
            index=self.get_index(),
            doc_type=self.get_doc_type(),
            id=instance.pk,
            body=self.prepare(instance)
        )

    def index_queryset(self, qs):
        index = self.get_index()
        doc_type = self.get_doc_type()

        actions = (
            {
                '_index': index,
                '_type': doc_type,
                '_id': instance.pk,
                '_source': self.prepare(instance),
            }
            for instance in qs.iterator()
        )

        return bulk(client = self.get_es(), actions=actions)

    def get_queryset(self):
        #Some objects have a default ordering, which only slows things down here.
        return self.model.objects.order_by()

    def get_filtered_queryset(self, since=None, until=None, limit=None):
        qs = self.get_queryset()
        filters = {}

        if since:
            filters["%s__gte" % self._meta.date_field] = since
        if until:
            filters["%s__lte" % self._meta.date_field] = until

        qs = qs.filter(**filters)

        if limit:
            qs = qs[:limit]

        return qs
    
    def should_index(self, instance):
        return self.get_queryset().filter(pk=instance.pk).exists()
    
    def __getattr__(self, attr):
        try:
            return getattr(self.get_search(), attr)
        except AttributeError:
            #Generate an exception message that refers to self
            return super(Index, self).__getattribute__(attr)
