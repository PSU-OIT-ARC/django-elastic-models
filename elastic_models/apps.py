from django.apps import AppConfig

class ElasticModelsConfig(AppConfig):
    name = 'elastic_models'
    verbose_name = "Elastic Models"
    
    def ready(self):
        from .receivers import register_receivers
        register_receivers()
