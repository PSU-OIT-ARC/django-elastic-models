import sys
from setuptools import find_packages, setup

setup(
    name='DjangoElasticModels',
    version='0.1',
    install_requires=['elasticsearch>=1.0.0,<2.0.0','elasticsearch-dsl<2.0.0'],
    packages=find_packages(),
    long_description=open('README.md').read(),
    author='Andrew Stoneman',
    extras_require={
        'test': ["django" + ("<1.7" if sys.version_info[:2] < (2, 7) else "")],
    }
)
