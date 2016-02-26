import sys

import django
from django.conf import settings


settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
        }
    },
    INSTALLED_APPS=(
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.admin',
        'elastic_models',
    ),
    MIDDLEWARE_CLASSES=[],
    ELASTICSEARCH_CONNECTIONS={
        'default': {
            'HOSTS': ['http://localhost:9200'],
            'INDEX_NAME': 'elastic_models_%s',
        }
    },
    TEMPLATES=[{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'loaders': [
                ('django.template.loaders.locmem.Loader', {
                    'test_index_template_name.txt': 'Template_{{ object.name }}',
                }),
            ],
        },
    }]
)

if django.VERSION[:2] >= (1, 7):
    from django import setup
else:
    setup = lambda: None

setup()

from elastic_models.tests import SearchRunner

test_runner = SearchRunner(verbosity=1)

failures = test_runner.run_tests(['elastic_models', ])
if failures:
    sys.exit(failures)
