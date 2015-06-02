"""
Flask-CloudStorage
"""

import os
import warnings
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from importlib import import_module
from flask import send_file, abort, url_for
import shortuuid
from libcloud.storage.types import Provider, ObjectDoesNotExistError
from libcloud.storage.providers import DRIVERS, get_driver
from libcloud.storage.base import Object as BaseObject, StorageDriver
from libcloud.storage.drivers import local
from six.moves.urllib.parse import urlparse, urlunparse, urljoin
import slugify

FILE_SERVER_ENDPOINT = "FLASK_CLOUDSTORAGE:FILE_SERVER"

EXTENSIONS = {
    "TEXT": ["txt"],
    "DOCUMENT": ["rtf", "odf", "ods", "gnumeric", "abw", "doc", "docx", "xls", "xlsx"],
    "IMAGE": ["jpg", "jpeg", "jpe", "png", "gif", "svg", "bmp"],
    "AUDIO": ["wav", "mp3", "aac", "ogg", "oga", "flac"],
    "DATA": ["csv", "ini", "json", "plist", "xml", "yaml", "yml"],
    "SCRIPT": ["js", "php", "pl", "py", "rb", "sh"],
    "ARCHIVE": ["gz", "bz2", "zip", "tar", "tgz", "txz", "7z"]
}

ALL_EXTENSIONS = EXTENSIONS["TEXT"] \
                 + EXTENSIONS["DOCUMENT"] \
                 + EXTENSIONS["IMAGE"] \
                 + EXTENSIONS["AUDIO"] \
                 + EXTENSIONS["DATA"] \
                 + EXTENSIONS["ARCHIVE"]

def get_file_name(filename):
    """
    Return the filename without the path
    :param filename:
    :return: str
    """
    return os.path.basename(filename)

def get_file_extension(filename):
    """
    Return a file extension
    :param filename:
    :return: str
    """
    return os.path.splitext(filename)[1][1:].lower()

def get_file_extension_type(filename):
    """
    Return the group associated to the file
    :param filename:
    :return: str
    """
    ext = get_file_extension(filename)
    if ext:
        for name, group in EXTENSIONS.items():
            if ext in group:
                return name
    return "OTHER"

def get_driver_class(provider):
    """
    Return the driver class
    :param provider: str - provider name
    :return:
    """
    if "." in provider:
        parts = provider.split('.')
        kls = parts.pop()
        path = '.'.join(parts)
        module = import_module(path)
        if not hasattr(module, kls):
            raise ImportError('{0} provider not found at {1}'.format(
                kls,
                path))
        driver = getattr(module, kls)
    else:
        driver = getattr(Provider, provider.upper())
    return get_driver(driver)

def get_provider_name(driver):
    """
    Return the provider name from the driver class
    :param driver: obj
    :return: str
    """
    kls = driver.__class__.__name__
    for d, prop in DRIVERS.items():
        if prop[1] == kls:
            return d
    return None


class InvalidExtensionError(Exception): pass


class Storage(object):
    _container_name = None
    _container = None
    _driver = None
    config = {}
    allowed_extensions = EXTENSIONS["TEXT"] \
                         + EXTENSIONS["DOCUMENT"] \
                         + EXTENSIONS["IMAGE"] \
                         + EXTENSIONS["AUDIO"] \
                         + EXTENSIONS["DATA"]

    def __init__(self, provider=None,
                 key=None,
                 secret=None,
                 container=None,
                 local_path=None,
                 allowed_extensions=None,
                 app=None,
                 secure_url=False,
                 **kwargs):

        """
        Initiate the storage
        :param provider: str - provider name
        :param key: str - provider key
        :param secret: str - provider secret
        :param container: str - the name of the container (bucket or a dir name if local)
        :param local_path: str - when provider == LOCAL, it is the base directory
        :param allowed_extensions: list - extensions allowed for upload
        :param app: Flask object -
        :param secure_url: bool - when getting the url, it will add https if true
        :param kwargs: any other params will pass to the provider initialization
        :return:
        """
        self.secure_url = secure_url

        if app:
            self.init_app(app)

        if allowed_extensions:
            self.allowed_extensions = allowed_extensions

        if provider:
            if not key and local_path:
                key = local_path

            kwparams = {
                "key": key,
                "secret": secret
            }

            kwparams.update(kwargs)
            self.driver = get_driver_class(provider)(**kwparams)

            if container:
                self.container = container

        self.local_path = local_path

    def init_app(self, app):
        """
        To initiate with Flask
        :param app: Flask object
        :return:
        """
        provider = app.config.get("CLOUDSTORAGE_PROVIDER", None)
        key = app.config.get("CLOUDSTORAGE_KEY", None)
        secret = app.config.get("CLOUDSTORAGE_SECRET", None)
        container = app.config.get("CLOUDSTORAGE_CONTAINER", None)
        local_path = app.config.get("CLOUDSTORAGE_LOCAL_PATH", None)
        allowed_extensions = app.config.get("CLOUDSTORAGE_ALLOWED_EXTENSIONS", None)
        secure_url = app.config.get("CLOUDSTORAGE_SERVE_FILES_URL_SECURE", False)
        serve_files = app.config.get("CLOUDSTORAGE_SERVE_FILES", False)
        serve_files_url = app.config.get("CLOUDSTORAGE_SERVE_FILES_URL", "files")

        self.config["serve_files"] = serve_files
        self.config["serve_files_url"] = serve_files_url

        if provider and provider.upper() == "LOCAL":
            if not local_path:
                raise ValueError("For 'LOCAL' provider, Storage requires CLOUDSTORAGE_LOCAL_PATH")
            else:
                key = local_path
                secret = None

        self.__init__(provider=provider,
                      key=key,
                      secret=secret,
                      container=container,
                      local_path=local_path,
                      allowed_extensions=allowed_extensions,
                      secure_url=secure_url)

        self._register_file_server(app)

    @property
    def driver(self):
        return self._driver

    @driver.setter
    def driver(self, driver):
        if not isinstance(driver, StorageDriver):
            raise AttributeError("Invalid Driver")
        self._driver = driver

    @property
    def container(self):
        return self._container

    @container.setter
    def container(self, container_name):
        self._container = self.driver.get_container(container_name)

    def __iter__(self):
        """
        Iterate over all the objects in the container
        :return: generator
        """
        for obj in self.container.iterate_objects():
            yield Object(obj=obj,
                         secure_url=self.secure_url,
                         local_path=self.local_path)

    def get_object(self, object_name, secure_url=None, validate=True, **kwargs):
        """
        Get the object
        :param object_name:
        :param secure_url: To secure url, when get_url
        :param validate: When False, it will build the object without validating it.
                        the object file may not exist in the container
        :param kwargs: When validate is False, these args will be pass
                        to the object builder
        :return: Object
        """
        if validate:
            obj = self.container.get_object(object_name)
        else:
            params = {
                "name": object_name,
                "size": kwargs.get("size", 0),
                "hash": kwargs.get("hash", None),
                "extra": kwargs.get("extra", None),
                "meta_data": kwargs.get("meta_data", None)
            }
            obj = BaseObject(container=self.container, driver=self.driver, **params)
        return Object(obj=obj,
                      secure_url=secure_url or self.secure_url,
                      local_path=self.local_path)

    def upload(self,
               file,
               name=None,
               prefix=None,
               allowed_extensions=None,
               overwrite=False,
               **kwargs):
        """
        To upload file
        :param file: FileStorage object or string location
        :param name: The name of the object.
        :param prefix: A prefix for the object. Can be in the form of directory tree
        :param allowed_extensions: list of extensions to allow
        :param overwrite: bool - To overwrite if file exists
        :param kwargs: extra params: ie: acl, meta_data etc.
        :return: Object
        """
        extra = kwargs

        # coming from an upload object
        if isinstance(file, FileStorage):
            extension = get_file_extension(file.filename)
            if not name:
                fname = get_file_name(file.filename).split("." + extension)[0]
                name = slugify.slugify(fname)
        else:
            extension = get_file_extension(file)
            if not name:
                name = get_file_name(file)

        if len(get_file_extension(name).strip()) == 0:
            name += "." + extension

        name = name.strip("/").strip()

        if isinstance(self.driver, local.LocalStorageDriver):
            name = secure_filename(name)

        if prefix:
            name = prefix.strip("/") + "/" + name

        if not overwrite:
            name = self._safe_object_name(name)

        if not allowed_extensions:
            allowed_extensions = self.allowed_extensions
        if extension.lower() not in allowed_extensions:
            raise InvalidExtensionError("Invalid file extension: '.%s' " % extension)

        if isinstance(file, FileStorage):
            obj = self.container.upload_object_via_stream(iterator=file,
                                               object_name=name,
                                               extra=extra)
        else:
            obj = self.container.upload_object(file_path=file,
                                               object_name=name,
                                               extra=extra)
        return Object(obj=obj,
                      secure_url=self.secure_url,
                      local_path=self.local_path)

    def object_exists(self, name):
        """
        Test if object exists
        :param name: the object name
        :return bool:
        """
        try:
            container_name = self.container.name
            self.driver.get_object(container_name, name)
            return True
        except ObjectDoesNotExistError:
            return False

    def _safe_object_name(self, object_name):
        """ Add a UUID if to a object name if it exists. To prevent overwrites
        :param object_name:
        :return str:
        """
        extension = get_file_extension(object_name)
        file_name = os.path.splitext(object_name)[0]
        while self.object_exists(object_name):
            uuid = shortuuid.uuid()
            object_name = "%s__%s.%s" % (file_name, uuid, extension)
        return object_name

    def _register_file_server(self, app):
        """
        File server
        Only local files can be served
        It's recommended to serve static files through NGINX instead of Python
        Use this for development only
        :param app: Flask app instance

        """
        if isinstance(self.driver, local.LocalStorageDriver) \
                and self.config["serve_files"]:
            server_url = self.config["serve_files_url"].strip("/").strip()
            if server_url:
                url = "/%s/<path:object_name>" % server_url

                @app.route(url, endpoint=FILE_SERVER_ENDPOINT)
                def files_server(object_name):
                    if self.object_exists(object_name):
                        obj = self.get_object(object_name)
                        _url = obj.get_cdn_url()
                        return send_file(_url, conditional=True)
                    else:
                        abort(404)
            else:
                warnings.warn("Flask-CloudStorage can't serve files. 'CLOUDSTORAGE_SERVER_FILES_URL' is not set")

class Object(object):
    """
    The object file

    @property
        name
        size
        hash
        extra
        meta_data

        driver
        container

    @method
        download()
        delete()
    """
    def __init__(self, obj, **kwargs):
        self._obj = obj
        self._kwargs = kwargs

    def __getattr__(self, item):
        return getattr(self._obj, item)

    def __len__(self):
        return self.size

    def get_url(self, secure_url=None):
        """
        Return the url 
        :param secure_url:
        :return:
        """
        secure = secure_url or self._kwargs.get("secure_url", False)
        driver_name = self.driver.name.lower()
        try:
            # Currently only Cloudfiles and Local supports it
            url = self._obj.get_cdn_url()
            if "local" in driver_name:
                url = url_for(FILE_SERVER_ENDPOINT,
                              object_name=self.name,
                              _external=True)
        except NotImplementedError as e:
            object_path = '%s/%s' % (self.container.name, self.name)
            if 's3' in driver_name:
                base_url = 'http://%s' % self.driver.connection.host
                url = urljoin(base_url, object_path)
            elif 'google' in driver_name:
                url = urljoin('http://storage.googleapis.com', object_path)
            elif 'azure' in driver_name:
                base_url = ('http://%s.blob.core.windows.net' % self.driver.key)
                url = urljoin(base_url, object_path)
            else:
                raise e

        if secure:
            if 'cloudfiles' in driver_name:
                parsed_url = urlparse(url)
                if parsed_url.scheme != 'http':
                    return url
                split_netloc = parsed_url.netloc.split('.')
                split_netloc[1] = 'ssl'
                url = urlunparse(
                    'https',
                    '.'.join(split_netloc),
                    parsed_url.path,
                    parsed_url.params, parsed_url.query,
                    parsed_url.fragment
                )
            if ('s3' in driver_name or
                    'google' in driver_name or
                    'azure' in driver_name):
                url = url.replace('http://', 'https://')
        return url

    @property
    def extension(self):
        """
        Return the extension of the object
        :return:
        """
        return get_file_extension(self.name)

    @property
    def type(self):
        """
        Return the object type (IMAGE, AUDIO,...) or OTHER
        :return:
        """
        return get_file_extension_type(self.name)

    @property
    def provider_name(self):
        """
        Return the provider name
        :return: str
        """
        return get_provider_name(self.driver)

    @property
    def container_name(self):
        """
        Return the container name
        :return: str
        """
        return self.container.name

    @property
    def local_path(self):
        """
        Return the local path for Local storage
        :return:
        """
        return self._kwargs.get("local_path", None)

    @property
    def object_path(self):
        """
        Return the object path
        :return: str
        """
        return '%s/%s' % (self.container.name, self.name)

