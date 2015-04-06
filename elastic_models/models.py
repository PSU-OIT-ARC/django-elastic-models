from __future__ import absolute_import
from __future__ import print_function
import six

from django.template.loader import render_to_string
from django.conf import settings
from django.db import models
from django.db.models.loading import get_model

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk
import elasticsearch_dsl as dsl


class SearchField(object):
    mapping = None
    mapping_type = 'string'
    #TODO: Add index, analyzer, etc.

    def get_mapping(self):
        if self.mapping is not None:
            return mapping

        return {
            'type': self.mapping_type
        }

    def get_from_instance(self, instance):
        return None

class TemplateField(SearchField):
    def __init__(self, template_name):
        self.template_name = template_name

    def get_from_instance(self, instance):
        context = {'object': self.instance}
        return render_to_string(template_name, context)

class AttributeField(SearchField):
    def __init__(self, attr):
        self.path = attr.split(".")

    def get_from_instance(self, instance):
        try:
            for attr in self.path:
                instance = getattr(instance, attr)
                if callable(instance):
                    instance = instance()
            return instance
        except AttributeError:
            return None

class StringField(AttributeField):
    def get_from_instance(self, instance):
        value = super(StringField, self).get_from_instance(instance)
        try:
            return six.text_type(value)
        except Exception as e:
            six.reraise(Exception, e)

class MultiField(AttributeField):
    def get_from_instance(self, instance):
        manager = super(MultiField, self).get_from_instance(instance)
        return u"\n".join(str(i) for i in manager.all())

class IntegerField(AttributeField):
    mapping_type = 'integer'

class BooleanField(AttributeField):
    mapping_type = 'boolean'

class DateField(AttributeField):
    mapping_type = 'date'

class SearchDescriptor(object):
    def __get__(self, instance, type=None):
        if instance != None:
            raise AttributeError("Search isn't accessible via %s instances" % type.__name__)
        return type._search_meta().get_search()


class SearchMixin(object):
    class Search(object):
        doc_type = None
        connection = 'default'
        mapping = None
        attribute_fields = ()
        template_fields = ()
        other_fields = {}
        index_by = 1000
        date_field = 'modified_on'

        # A dictionary whose keys are other models that this model's index
        # depends on, and whose values are query set paramaters for this model
        # to select the instances that depend on an instance of the key model.
        # For example, the index for BlogPost might use information from Author,
        # so it would have dependencies = {Author: 'author'}.
        # When an Author is saved, this causes BlogPost's returned by the query
        # BlogPost.objects.filter(author=instance) to be re-indexed.
        dependencies = {}

        def __init__(self, model):
            self.model = model

        def get_index(self):
            return settings.ELASTICSEARCH_CONNECTIONS[self.connection]['INDEX_NAME']

        def get_doc_type(self):
            if self.doc_type is not None:
                return self.doc_type
            else:
                return "%s_%s" % (self.model._meta.app_label, self.model._meta.model_name)

        def get_dependencies(self):
            dependencies = self.dependencies
            for model, query in dependencies.items():
                if isinstance(model, six.string_types):
                    (app_name, model_name) = model.split('.')
                    model_cls = get_model(app_name, model_name)
                    dependencies.pop(model)
                    dependencies[model_cls] = query
            return dependencies

        def get_es(self):
            return Elasticsearch(settings.ELASTICSEARCH_CONNECTIONS[self.connection]['HOSTS'])

        def get_search(self):
            s = dsl.Search(using=self.get_es())
            s = s.index(self.get_index())
            s = s.doc_type(self.get_doc_type())
            return s

        def get_attr_field(self, attr):
            # Figure out if the attribute is a model field, and if so, use it to
            # determine the search index field type.

            model = self.model
            path = attr.split(".")
            name = path[-1]
            try:
                for a in path[:-1]:
                    model = model._meta.get_field(a).rel.to
                field = model._meta.get_field_by_name(path[-1])[0]

                if isinstance(field, models.BooleanField):
                    return name, BooleanField(attr=attr)
                elif isinstance(field, models.IntegerField):
                    return name, IntegerField(attr=attr)
                elif isinstance(field, models.DateField):
                    return name, DateField(attr=attr)
                elif isinstance(field, (models.ManyToManyField, models.related.RelatedObject)):
                    return name, MultiField(attr=attr)
                else:
                    return name, StringField(attr=attr)

            except (AttributeError, models.FieldDoesNotExist):
                return name, StringField(attr=attr)


        def get_fields(self):
            fields = {
                'pk': IntegerField(attr="pk")
            }

            for attr in self.attribute_fields:
                name, field = self.get_attr_field(attr)
                fields[name] = field

            for name in self.template_fields:
                fields[name] = TemplateField(
                    template_name = "search/indexes/%s/%s_%s.html" %
                                    (self.model._meta.app_label, self.model._meta.model_name, name)
                )

            fields.update(self.other_fields)

            return fields

        def put_mapping(self):
            properties = dict((name, field.get_mapping())
                              for name, field in self.get_fields().items())
            mapping = {
                'properties': properties
            }

            es = self.get_es()

            try:
                es.indices.delete_mapping(index=self.get_index(), doc_type=self.get_doc_type())
            except NotFoundError:
                pass

            try:
                es.indices.put_mapping(index=self.get_index(), doc_type=self.get_doc_type(), body=mapping)
            except NotFoundError:
                es.indices.create(index=self.get_index())
                es.indices.put_mapping(index=self.get_index(), doc_type=self.get_doc_type(), body=mapping)

        def prepare(self, instance):
            return dict((name, field.get_from_instance(instance))
                        for name, field in self.get_fields().items())

        def index_instance(self, instance):
            self.get_es().index(
                index=self.get_index(),
                doc_type=self.get_doc_type(),
                id=instance.pk,
                body=self.prepare(instance)
            )

        def index_qs(self, qs):
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

        def get_base_qs(self):
            #Some objects have a default ordering, which only slows things down here.
            return self.model.objects.order_by()

        def get_qs(self, since=None, until=None, limit=None):
            qs = self.get_base_qs()
            filters = {}

            if since:
                filters["%s__gte" % self.date_field] = since
            if until:
                filters["%s__lte" % self.date_field] = until

            qs = qs.filter(**filters)

            if limit:
                qs = qs[:limit]

            return qs

    @classmethod
    def _search_meta(cls):
        return cls.Search(cls)

    search = SearchDescriptor()

    def index(self):
        return self._search_meta().index_instance(self)
