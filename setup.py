from setuptools import find_packages, setup

setup(
    name='DjangoElasticModels',
    version='0.1',
    install_requires=['elasticsearch','elasticsearch-dsl'],
    packages=find_packages(),
    long_description=open('README.md').read(),
    author='Andrew Stoneman'
)
