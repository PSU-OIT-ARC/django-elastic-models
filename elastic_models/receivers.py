import logging
from contextlib import contextmanager
from datetime import timedelta

from django.db.models.signals import post_save
from django.db import models
from django.dispatch import receiver
from django.utils.timezone import now

from .indexes import index_registry

#A list of sets to allow nested/concurent use
suspended_models = []

def get_search_models():
    return set(m for (m, a) in index_registry.keys())

def is_suspended(model):
    for models in suspended_models:
        if model in models:
            return True
    return False

@receiver(post_save)
def update_search_index(sender, **kwargs):
    if is_suspended(sender):
        return
    
    instance = kwargs['instance']
    
    for index in index_registry.values():
        if issubclass(sender, index.model) and index.should_index(instance):
            index.index_instance(instance)
            continue
        
        dependencies = index.get_dependencies()
        if sender in dependencies:
            filter_kwargs = {
                dependencies[sender]: instance
            }
            qs = search_meta.get_queryset().filter(**filter_kwargs)
            search_meta.index_queryset(qs)


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

            
