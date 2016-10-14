"""
Flask-Cloudy
"""

import os
import datetime
import base64
import hmac
import hashlib
import warnings
from contextlib import contextmanager
import copy
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from importlib import import_module
from flask import send_file, abort, url_for, request
import shortuuid
from libcloud.storage.types import Provider, ObjectDoesNotExistError
from libcloud.storage.providers import DRIVERS, get_driver
from libcloud.storage.base import Object as BaseObject, StorageDriver
from libcloud.storage.drivers import local
from six.moves.urllib.parse import urlparse, urlunparse, urljoin, urlencode
import slugify


SERVER_ENDPOINT = "FLASK_CLOUDY_SERVER"

EXTENSIONS = {
    "TEXT": ["txt", "md"],
    "DOCUMENT": ["rtf", "odf", "ods", "gnumeric", "abw", "doc", "docx", "xls", "xlsx"],
    "IMAGE": ["jpg", "jpeg", "jpe", "png", "gif", "svg", "bmp", "webp"],
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

class InvalidExtensionError(Exception):
    pass

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


class Storage(object):
    container = None
    driver = None
    config = {}
    allowed_extensions = EXTENSIONS["TEXT"] \
                         + EXTENSIONS["DOCUMENT"] \
                         + EXTENSIONS["IMAGE"] \
                         + EXTENSIONS["AUDIO"] \
                         + EXTENSIONS["DATA"]
    _kw = {}

    def __init__(self,
                 provider=None,
                 key=None,
                 secret=None,
                 container=None,
                 allowed_extensions=None,
                 app=None,
                 **kwargs):

        """
        Initiate the storage
        :param provider: str - provider name
        :param key: str - provider key
        :param secret: str - provider secret
        :param container: str - the name of the container (bucket or a dir name if local)
        :param allowed_extensions: list - extensions allowed for upload
        :param app: object - Flask instance
        :param kwargs: any other params will pass to the provider initialization
        :return:
        """

        if app:
            self.init_app(app)

        if provider:
            # Hold the params that were passed
            self._kw = {
                "provider": provider,
                "key": key,
                "secret": secret,
                "container": container,
                "allowed_extensions": allowed_extensions,
                "app": app
            }
            self._kw.update(kwargs)

            if allowed_extensions:
                self.allowed_extensions = allowed_extensions

            kwparams = {
                "key": key,
                "secret": secret
            }

            if "local" in provider.lower():
                kwparams["key"] = container
                container = ""

            kwparams.update(kwargs)

            self.driver = get_driver_class(provider)(**kwparams)
            if not isinstance(self.driver, StorageDriver):
                raise AttributeError("Invalid Driver")

            self.container = self.driver.get_container(container)

    def __iter__(self):
        """
        ie: `for item in storage`
        Iterate over all the objects in the container
        :return: generator
        """
        for obj in self.container.iterate_objects():
            yield Object(obj=obj)

    def __len__(self):
        """
        ie: `len(storage)`
        Return the total objects in the container
        :return: int
        """
        return len(self.container.list_objects())

    def __contains__(self, object_name):
        """
        ie: `if name in storage` or `if name not in storage`
        Test if object exists
        :param object_name: the object name
        :return bool:
        """
        try:
            self.driver.get_object(self.container.name, object_name)
            return True
        except ObjectDoesNotExistError:
            return False

    def init_app(self, app):
        """
        To initiate with Flask
        :param app: Flask object
        :return:
        """
        provider = app.config.get("STORAGE_PROVIDER", None)
        key = app.config.get("STORAGE_KEY", None)
        secret = app.config.get("STORAGE_SECRET", None)
        container = app.config.get("STORAGE_CONTAINER", None)
        allowed_extensions = app.config.get("STORAGE_ALLOWED_EXTENSIONS", None)
        serve_files = app.config.get("STORAGE_SERVER", True)
        serve_files_url = app.config.get("STORAGE_SERVER_URL", "files")

        self.config["serve_files"] = serve_files
        self.config["serve_files_url"] = serve_files_url

        if not provider:
            raise ValueError("'STORAGE_PROVIDER' is missing")

        if provider.upper() == "LOCAL":
            if not os.path.isdir(container):
                raise IOError("Local Container (directory) '%s' is not a "
                              "directory or doesn't exist for LOCAL provider" % container)

        self.__init__(provider=provider,
                      key=key,
                      secret=secret,
                      container=container,
                      allowed_extensions=allowed_extensions)

        self._register_file_server(app)

    @contextmanager
    def use(self, container):
        """
        A context manager to temporarily use a different container on the same driver
        :param container: str - the name of the container (bucket or a dir name if local)
        :yield: Storage
        """
        kw = self._kw.copy()
        kw["container"] = container
        s = Storage(**kw)
        yield s
        del s

    def get(self, object_name):
        """
        Return an object or None if it doesn't exist
        :param object_name:
        :return: Object
        """
        if object_name in self:
            return Object(obj=self.container.get_object(object_name))
        return None

    def create(self, object_name, size=0, hash=None, extra=None, meta_data=None):
        """
        create a new object

        :param object_name:
        :param size:
        :param hash:
        :param extra:
        :param meta_data:
        :return: Object
        """
        obj = BaseObject(container=self.container,
                         driver=self.driver,
                         name=object_name,
                         size=size,
                         hash=hash,
                         extra=extra,
                         meta_data=meta_data)
        return Object(obj=obj)

    def upload(self,
               file,
               name=None,
               prefix=None,
               allowed_extensions=None,
               overwrite=False,
               public=False,
               **kwargs):
        """
        To upload file
        :param file: FileStorage object or string location
        :param name: The name of the object.
        :param prefix: A prefix for the object. Can be in the form of directory tree
        :param allowed_extensions: list of extensions to allow
        :param overwrite: bool - To overwrite if file exists
        :param public: bool - To set acl to private or public-read. Having acl in kwargs will override it
        :param kwargs: extra params: ie: acl, meta_data etc.
        :return: Object
        """
        if "acl" not in kwargs:
            kwargs["acl"] = "public-read" if public else "private"
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
            name = prefix.lstrip("/") + name

        if not overwrite:
            name = self._safe_object_name(name)

        if not allowed_extensions:
            allowed_extensions = self.allowed_extensions
        if extension.lower() not in allowed_extensions:
            raise InvalidExtensionError("Invalid file extension: '.%s' " % extension)

        if isinstance(file, FileStorage):
            obj = self.container.upload_object_via_stream(iterator=file.stream,
                                                          object_name=name,
                                                          extra=extra)
        else:
            obj = self.container.upload_object(file_path=file,
                                               object_name=name,
                                               extra=extra)
        return Object(obj=obj)

    def _safe_object_name(self, object_name):
        """ Add a UUID if to a object name if it exists. To prevent overwrites
        :param object_name:
        :return str:
        """
        extension = get_file_extension(object_name)
        file_name = os.path.splitext(object_name)[0]
        while object_name in self:
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

                @app.route(url, endpoint=SERVER_ENDPOINT)
                def files_server(object_name):
                    obj = self.get(object_name)
                    if obj is not None:
                        dl = request.args.get("dl")
                        name = request.args.get("name", obj.name)

                        if get_file_extension(name) != obj.extension:
                            name += ".%s" % obj.extension

                        _url = obj.get_cdn_url()
                        return send_file(_url,
                                         as_attachment=True if dl else False,
                                         attachment_filename=name,
                                         conditional=True)
                    else:
                        abort(404)
            else:
                warnings.warn("Flask-Cloudy can't serve files. 'STORAGE_SERVER_FILES_URL' is not set")

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
        download() use save_to() instead
        delete()
    """

    _obj = None

    def __init__(self, obj, **kwargs):
        self._obj = obj
        self._kwargs = kwargs

    def __getattr__(self, item):
        return getattr(self._obj, item)

    def __len__(self):
        return self.size

    def get_url(self, secure=False, longurl=False):
        """
        Return the url 
        :param secure: bool - To use https
        :param longurl: bool - On local, reference the local path with the domain
                        ie: http://site.com/files/object.png otherwise /files/object.png
        :return: str
        """
        driver_name = self.driver.name.lower()
        try:
            # Currently only Cloudfiles and Local supports it
            url = self._obj.get_cdn_url()
            if "local" in driver_name:
                url = url_for(SERVER_ENDPOINT,
                              object_name=self.name,
                              _external=longurl)
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
    def url(self):
        """
        Returns the url of the object.
        For Local it will return it without the domain name
        :return: str
        """
        return self.get_url()

    @property
    def full_url(self):
        """
        Returns the full url with the domain, specially for Local storage
        :return: str
        """
        return self.get_url(longurl=True)


    @property
    def secure_url(self):
        """
        Return the full url with https
        :return:
        """
        return self.get_url(secure=True, longurl=True)

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
    def path(self):
        """
        Return the object path
        :return: str
        """
        return "%s/%s" % (self.container.name, self.name)

    @property
    def full_path(self):
        """
        Return the full path of the local object
        If not local, it will return self.path
        :return: str
        """
        if "local" in self.driver.name.lower():
            return "%s/%s" % self.container.key, self.path
        return self.path

    def save_to(self, destination, name=None, overwrite=False, delete_on_failure=True):
        """
        To save the object in a local path
        :param destination: str - The directory to save the object to
        :param name: str - To rename the file name. Do not add extesion
        :param overwrite:
        :param delete_on_failure:
        :return: The new location of the file or None
        """
        if not os.path.isdir(destination):
            raise IOError("'%s' is not a valid directory")

        obj_path = "%s/%s" % (destination, self._obj.name)
        if name:
            obj_path = "%s/%s.%s" % (destination, name, self.extension)

        file = self._obj.download(obj_path,
                                  overwrite_existing=overwrite,
                                  delete_on_failure=delete_on_failure)
        return obj_path if file else None

    def download_url(self, timeout=60, name=None):
        """
        Trigger a browse download
        :param timeout: int - Time in seconds to expire the download
        :param name: str - for LOCAL only, to rename the file being downloaded
        :return: str
        """
        if "local" in self.driver.name.lower():
            return url_for(SERVER_ENDPOINT,
                           object_name=self.name,
                           dl=1,
                           name=name,
                           _external=True)
        else:
            driver_name = self.driver.name.lower()
            expires = (datetime.datetime.now()
                       + datetime.timedelta(seconds=timeout)).strftime("%s")

            if 's3' in driver_name or 'google' in driver_name:

                s2s = "GET\n\n\n{expires}\n/{object_name}"\
                    .format(expires=expires, object_name=self.path)
                h = hmac.new(self.driver.secret, s2s, hashlib.sha1)
                s = base64.encodestring(h.digest()).strip()
                _keyIdName = "AWSAccessKeyId" if "s3" in driver_name else "GoogleAccessId"
                params = {
                    _keyIdName: self.driver.key,
                    "Expires": expires,
                    "Signature": s
                }
                urlkv = urlencode(params)
                return "%s?%s" % (self.secure_url, urlkv)

            elif 'cloudfiles' in driver_name:
                return self.driver.ex_get_object_temp_url(self._obj,
                                                               method="GET",
                                                               timeout=expires)
            else:
                raise NotImplemented("This provider '%s' doesn't support or "
                                     "doesn't have a signed url "
                                     "implemented yet" % self.provider_name)
