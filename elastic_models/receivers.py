import logging
from contextlib import contextmanager
from datetime import timedelta

from django.db.models.signals import post_save
from django.db import models
from django.dispatch import receiver
from django.utils.timezone import now


#A list of sets to allow nested/concurent use
suspended_models = []

def get_search_models():
    from .models import SearchMixin
    return [m for m in models.get_models() if issubclass(m, SearchMixin) and 'Search' in m.__dict__]

def is_suspended(model):
    for models in suspended_models:
        if model in models:
            return True
    return False

@receiver(post_save)
def update_search_index(sender, **kwargs):
    if is_suspended(sender):
        return
    
    search_models = get_search_models()
    instance = kwargs['instance']
    
    if sender in search_models:
        instance.index()
    
    for model in search_models:
        search_meta = model._search_meta()
        dependencies = search_meta.get_dependencies()
        if sender in dependencies:
            filter_kwargs = {
                dependencies[sender]: instance
            }
            search_meta.index_qs(search_meta.get_qs().filter(**filter_kwargs))


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
        
        for model in search_models:
            search_meta = model._search_meta()
            if model in models or models.intersection(search_meta.dependencies):
                qs = search_meta.get_qs(since=start)
                search_meta.index_qs(qs)

            
