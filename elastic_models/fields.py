from django.template.loader import render_to_string
from django.db import models
from django.utils import six

class SearchField(object):
    mapping = None
    mapping_type = 'string'
    #TODO: Add index, analyzer, etc.

    # Tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0

    def __init__(self):
        self.creation_counter = SearchField.creation_counter
        SearchField.creation_counter += 1

    def get_field_mapping(self):
        if self.mapping is not None:
            return mapping

        return {
            'type': self.mapping_type
        }

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
    def __init__(self, attr):
        super(AttributeField, self).__init__()
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

class JoinedStringField(AttributeField):
    def __init__(self, attr, sep=u"\n"):
        self.sep = sep
        
    def get_from_instance(self, instance):
        manager = super(MultiField, self).get_from_instance(instance)
        return self.sep.join(str(i) for i in manager.all())

class IntegerField(AttributeField):
    mapping_type = 'integer'

class BooleanField(AttributeField):
    mapping_type = 'boolean'

class DateField(AttributeField):
    mapping_type = 'date'



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

class FieldMappingMixin(six.with_metaclass(DeclarativeSearchFieldMetaclass)):
    _options_class = None
    
    def __init__(self, *args, **kwargs):
        if 'attribute_fields' in kwargs:
            self.attribute_fields = kwargs.pop('attribute_fields')

        if 'template_fields' in kwargs:
            self.template_fields = kwargs.pop('template_fields')

        if 'other_fields' in kwargs:
            self.other_fields = kwargs.pop('other_fields')

        super(FieldMappingMixin, self).__init__(*args, **kwargs)

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
                return name, JoinedStringField(attr=attr)
            else:
                return name, StringField(attr=attr)

        except (AttributeError, models.FieldDoesNotExist):
            return name, StringField(attr=attr)


    def get_fields(self):
        fields = {
            'pk': IntegerField(attr="pk")
        }

        for attr in self._meta.attribute_fields:
            name, field = self.get_attr_field(attr)
            fields[name] = field

        for name in self._meta.template_fields:
            fields[name] = TemplateField(
                template_name = "search/indexes/%s/%s_%s_%s.html" %
                                (self.model._meta.app_label, self.model._meta.model_name, self.name, name)
            )

        fields.update(self.declared_fields)

        return fields

    def get_mapping(self):
        properties = dict((name, field.get_field_mapping())
                          for name, field in list(self.fields.items()))
        mapping = {
            'properties': properties
        }
        return mapping

    def prepare(self, instance):
        return dict((name, field.get_from_instance(instance))
                    for name, field in self.fields.items())
