from django.template.loader import render_to_string
from django.db import models
from django.utils import six

import elasticsearch_dsl as dsl

from .utils import merge, getattr_or_callable

class SearchField(object):
    dsl_field = dsl.String
    
    # Tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0
    
    def __init__(self, **kwargs):
        self.creation_counter = SearchField.creation_counter
        SearchField.creation_counter += 1
        self.field_kwargs = kwargs

    def get_dsl_field(self):
        return self.dsl_field(**self.field_kwargs)
    
    def get_field_settings(self):
        return {}
    
    def get_from_instance(self, instance):
        return None


class TemplateField(SearchField):
    def __init__(self, template_name):
        super(TemplateField, self).__init__()
        self.template_name = template_name

    def get_from_instance(self, instance):
        context = {'object': self.instance}
        return render_to_string(template_name, context)


class AttributeField(SearchField):
    def __init__(self, attr, **kwargs):
        super(AttributeField, self).__init__(**kwargs)
        self.path = attr.split(".")
    
    def get_attr_from_instance(self, instance):
        try:
            for attr in self.path:
                instance = getattr_or_callable(instance, attr)
            return instance
        except AttributeError:
            return None
    
    def prepare(self, value):
        return value
    
    def get_from_instance(self, instance):
        value = self.get_attr_from_instance(instance)
        return self.prepare(value)


class ListMixin(AttributeField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('multi', True)
        super(ListMixin, self).__init__(*args, **kwargs)
    
    def get_from_instance(self, instance):
        values = self.get_attr_from_instance(instance)
        if hasattr(values, 'all'):
            values = values.all()
        return [self.prepare(v) for v in values]


class StringField(AttributeField):
    def prepare(self, value):
        return six.text_type(value)

class StringListField(ListMixin, StringField):
    pass

class IntegerField(AttributeField):
    dsl_field = dsl.Integer

class IntegerListField(ListMixin, IntegerField):
    pass

class BooleanField(AttributeField):
    dsl_field = dsl.Boolean

class BooleanListField(ListMixin, BooleanField):
    pass

class DateField(AttributeField):
    dsl_field = dsl.Date

class DateListField(ListMixin, DateField):
    pass



class DeclarativeSearchFieldMetaclass(type):
    """
    Metaclass that converts Field attributes to a dictionary called
    'declared_fields', taking into account parent class 'declared_fields' as
    well.
    """
    def __new__(cls, name, bases, attrs):
        fields = [(field_name, attrs.pop(field_name))
                  for field_name, obj in list(six.iteritems(attrs))
                  if isinstance(obj, SearchField)]
        fields.sort(key=lambda x: x[1].creation_counter)

        for base in bases[::-1]:
            if hasattr(base, 'declared_fields'):
                fields = list(six.iteritems(base.declared_fields)) + fields

        field_dict = dict(fields)

        for k in list(six.iterkeys(field_dict)):
            if k in attrs and attrs[k] is None:
                del field_dict[k]

        attrs['declared_fields'] = field_dict

        new_class = super(DeclarativeSearchFieldMetaclass, cls).__new__(cls, name, bases, attrs)
        
        
        OptionsClass = new_class._options_class
        if OptionsClass:
            options_list = [c.Meta for c in new_class.mro() if hasattr(c, 'Meta')]
            new_class._meta = OptionsClass(options_list)
        
        return new_class

class FieldMappingOptions(object):
    def __init__(self, sources=[]):
        self.mapping = self.get_value(sources, 'mapping', None)
        self.attribute_fields = self.get_value(sources, 'attribute_fields', ())
        self.template_fields = self.get_value(sources, 'template_fields', ())

    def get_value(self, sources, name, default):
        for source in sources:
            try:
                return getattr(source, name)
            except AttributeError:
                continue
        return default

class FieldMappingMixin(six.with_metaclass(DeclarativeSearchFieldMetaclass)):
    _options_class = FieldMappingOptions
    
    pk = IntegerField(attr="pk")
    
    def __init__(self, *args, **kwargs):
        if 'attribute_fields' in kwargs:
            self._attribute_fields = kwargs.pop('attribute_fields')

        if 'template_fields' in kwargs:
            self._template_fields = kwargs.pop('template_fields')

        if 'other_fields' in kwargs:
            self._other_fields = kwargs.pop('other_fields')

        super(FieldMappingMixin, self).__init__(*args, **kwargs)

    def get_attr_field(self, attr):
        # Figure out if the attribute is a model field, and if so, use it to
        # determine the search index field type.
        
        path = attr.split(".")
        name = path[-1]
        try:
            model = self.model
            
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
                return name, JoinedStringField(attr=attr)
            else:
                return name, StringField(attr=attr)

        except (AttributeError, models.FieldDoesNotExist):
            return name, StringField(attr=attr)

    
    def get_template_field_name(self, name):
        return "search/indexes/%s/%s_%s.html" %(
            self.model._meta.app_label,
            self.model._meta.model_name,
            name
        )
    
    def get_fields(self):
        fields = {}
        
        for attr in self._meta.attribute_fields:
            name, field = self.get_attr_field(attr)
            fields[name] = field
        
        for attr in getattr(self, '_attribute_fields', ()):
            name, field = self.get_attr_field(attr)
            fields[name] = field

        for name in self._meta.template_fields:
            fields[name] = TemplateField(
                template_name = self.get_template_field_name(name)
            )
        
        for name in getattr(self, '_template_fields', ()):
            fields[name] = TemplateField(
                template_name = self.get_template_field_name(name)
            )

        fields.update(self.declared_fields)
        
        fields.update(getattr(self, '_other_fields', {}))

        return fields
    
    def add_fields_to_mapping(self, mapping):
        for name, field in self.fields.items():
            mapping.field(name, field.get_dsl_field())
    
    def get_settings(self):
        return merge([f.get_field_settings() for f in self.fields.values()])
    
    def prepare(self, instance):
        return dict((name, field.get_from_instance(instance))
                    for name, field in self.fields.items())

class ObjectField(FieldMappingMixin, AttributeField):
    dsl_field = dsl.Object
    
    def __init__(self, *args, **kwargs):
        if 'model' in kwargs:
            self.model = kwargs.pop('model')
        
        super(ObjectField, self).__init__(*args, **kwargs)
        self.fields = self.get_fields()
    
    def get_dsl_field(self):
        field = super(ObjectField, self).get_dsl_field()
        self.add_fields_to_mapping(field)
        return field

class NestedObjectListField(ListMixin, ObjectField):
    dsl_field = dsl.Nested
