import logging
from contextlib import contextmanager
from datetime import timedelta

from django.db.models import signals
from django.db import models
from django.dispatch import receiver
from django.utils.timezone import now

from .indexes import index_registry

#A list of sets to allow nested/concurent use
suspended_models = []

def get_search_models():
    return set(m for (m, a) in index_registry.keys())

def get_indexes_for_model(model):
    return [i for (m, n), i in index_registry.items() if issubclass(model, m)]

def is_suspended(model):
    for models in suspended_models:
        if model in models:
            return True
    return False


def get_dependents(instance):
    dependents = {}
    for index in index_registry.values():
        dependencies = index.get_dependencies()
        if type(instance) in dependencies:
            filter_kwargs = {dependencies[type(instance)]: instance}
            qs = index.model.objects.filter(**filter_kwargs)
            dependents[index] = list(qs.values("pk"))

    return dependents

@receiver(signals.pre_save)
@receiver(signals.pre_delete)
def collect_dependents(sender, **kwargs):
    instance = kwargs['instance']
    instance._search_dependents = get_dependents(instance)

@receiver(signals.post_delete)
@receiver(signals.post_save)
def update_search_index(sender, **kwargs):
    """
    TBD
    """
    search_models = get_search_models()
    instance = kwargs['instance']
    indexes = get_indexes_for_model(sender)
    
    if _is_suspended(sender):
        logger.debug("Skipping indexing for '%s'" % (sender))
        return

    for index in indexes:
        index.index_instance(instance)

    dependents = merge([instance._search_dependents, get_dependents(instance)])
    for index, pks in six.iteritems(dependents):
        for record in index.model.objects.filter(pk__in=pks).iterator():
            index.index_instance(record)

@receiver(signals.m2m_changed)
def handle_m2m(sender, **kwargs):
    if kwargs['action'].startswith("pre_"):
        collect_dependents(type(kwargs['instance']), **kwargs)
    else:
        update_search_index(type(kwargs['instance']), **kwargs)


# @receiver(post_save)
# def update_search_index(sender, **kwargs):
#     if is_suspended(sender):
#         return
#
#     instance = kwargs['instance']
#
#     for index in index_registry.values():
#         if issubclass(sender, index.model) and index.should_index(instance):
#             index.index_instance(instance)
#             continue
#
#         dependencies = index.get_dependencies()
#         if sender in dependencies:
#             filter_kwargs = {
#                 dependencies[sender]: instance
#             }
#             qs = index.get_queryset().filter(**filter_kwargs)
#             index.index_queryset(qs)


SUSPENSION_BUFFER_TIME = timedelta(seconds=10)

@contextmanager
def suspended_updates(models=None):
    search_models = get_search_models()
    
    if not models:
        models = search_models
    
    models = set(models)
    
    start = now() - SUSPENSION_BUFFER_TIME
    suspended_models.append(models)
    
    try:
        yield
    finally:
        suspended_models.remove(models)
        
        for index in index_registry.values():
            if index.model in models or models.intersection(index.get_dependencies()):
                qs = index.get_filtered_queryset(since=start)
                index.index_queryset(qs)

            
