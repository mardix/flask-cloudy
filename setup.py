"""
Flask-Cloudy

A wrapper around Apache-Libcloud to upload and save files on cloud storage
providers such as: AWS S3, Google Storage, Microsoft Azure, Rackspace Cloudfiles,
and even on local storage through a Flask application.
(It can be used as standalone)

Supported storage:

- AWS S3
- Google Storage
- Microsoft Azure
- Rackspace CloudFiles
- Local

"""

from setuptools import setup, find_packages

__NAME__ = "Flask-Cloudy"
__version__ = "0.15.0"
__author__ = "Mardix"
__license__ = "MIT"
__copyright__ = "2016"

setup(
    name=__NAME__,
    version=__version__,
    license=__license__,
    author=__author__,
    author_email='mardix@github.com',
    description="Flask-Cloudy is a simple flask extension and standalone library to upload and save files on S3, Google storage or other Cloud Storages",
    long_description=__doc__,
    url='https://github.com/mardix/flask-cloudy/',
    download_url='http://github.com/mardix/flask-cloudy/tarball/master',
    py_modules=['flask_cloudy'],
    include_package_data=True,
    packages=find_packages(),
    install_requires=[
        "Flask>=0.10.1",
        "apache-libcloud==0.20.0",
        "lockfile==0.10.2",
        "shortuuid==0.1",
        "six==1.9.0",
        'python-slugify==0.1.0'
    ],

    keywords=["flask", "s3", "aws", "cloudfiles", "storage", "azure", "google", "cloudy"],
    platforms='any',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    zip_safe=False
)

