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
            'INDEX_NAME': 'elastic_models',
        }
    }
)

if django.VERSION[:2] >= (1, 7):
    from django import setup
else:
    setup = lambda: None

from elastic_models.tests import DefaultSearchRunner

setup()
test_runner = DefaultSearchRunner(verbosity=1)

failures = test_runner.run_tests(['elastic_models', ])
if failures:
    sys.exit(failures)
