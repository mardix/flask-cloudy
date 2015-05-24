"""
Flask-CloudStorage
"""

import os
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from importlib import import_module
import shortuuid
from libcloud.storage.types import Provider, ObjectDoesNotExistError
from libcloud.storage.providers import get_driver
from libcloud.storage.base import Object
from libcloud.storage.drivers.local import LocalStorageDriver


# Extension
EXTENSIONS = {
    "TEXT": ["txt"],
    "DOCUMENT": ["rtf", "odf", "ods", "gnumeric", "abw", "doc", "docx", "xls", "xlsx"],
    "IMAGE": ["jpg", "jpeg", "jpe", "png", "gif", "svg", "bmp"],
    "AUDIO": ["wav", "mp3", "aac", "ogg", "oga", "flac"],
    "DATA": ["csv", "ini", "json", "plist", "xml", "yaml", "yml"],
    "SCRIPTS": ["js", "php", "pl", "py", "rb", "sh"],
    "ARCHIVES": ["gz", "bz2", "zip", "tar", "tgz", "txz", "7z"]
}

ALL_EXTENSIONS = EXTENSIONS["TEXT"] \
                 + EXTENSIONS["DOCUMENT"] \
                 + EXTENSIONS["IMAGE"] \
                 + EXTENSIONS["AUDIO"] \
                 + EXTENSIONS["DATA"]

def get_file_name(filename):
    return os.path.basename(filename)

def get_file_extension(filename):
    return os.path.splitext(filename)[1][1:].lower()

def get_file_extension_type(filename):
    ext = get_file_extension(filename)
    if ext:
        for name, group in EXTENSIONS.items():
            if ext in group:
                return name
    return "OTHER"

class InvalidExtensionError(Exception):
    pass

class Storage(object):
    _container_name = None
    _container = None
    _driver = None
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
                 **kwargs):
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
            self.driver = self.get_driver_class(provider)(**kwparams)

            if container:
                self.container = container

    def init_app(self, app):
        """
        To initiate with Flask
        :param app:
        :return:
        """
        provider = app.config.get("CLOUDSTORAGE_PROVIDER", None)
        key = app.config.get("CLOUDSTORAGE_KEY", None)
        secret = app.config.get("CLOUDSTORAGE_SECRET", None)
        container = app.config.get("CLOUDSTORAGE_CONTAINER", None)
        local_path = app.config.get("CLOUDSTORAGE_LOCAL_PATH", None)
        allowed_extensions = app.config.get("CLOUDSTORAGE_ALLOWED_EXTENSIONS", None)

        if provider.upper() == "LOCAL":
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
                      allowed_extensions=allowed_extensions)

    @property
    def driver(self):
        return self._driver

    @driver.setter
    def driver(self, driver):
        self._driver = driver

    @property
    def container(self):
        return self._container

    @container.setter
    def container(self, container_name):
        self._container = self.driver.get_container(container_name)

    def __iter__(self):
        """
        Iterate over all the files in the container
        :return: generator
        """
        for obj in self.container.iterate_objects():
            yield Object(obj, cloudstorage=self)

    @classmethod
    def get_driver_class(cls, provider):
        if "." not in provider:
            driver = getattr(Provider, provider.upper())
        else:
            parts = provider.split('.')
            kls = parts.pop()
            path = '.'.join(parts)
            module = import_module(path)
            if not hasattr(module, kls):
                raise ImportError('{0} provider not found at {1}'.format(
                    kls,
                    path))
            driver = getattr(module, kls)
        return get_driver(driver)

    def object(self, object_name, size=0, hash=None, extra=None, meta_data={}):
        obj = Object(name=object_name,
                         size=size,
                         hash=hash,
                         extra=extra,
                         meta_data=meta_data,
                         container=self.container,
                         driver=self.driver)
        return StorageObject(obj=obj, cloudstorage=self)

    def upload(self,
               file,
               object_name=None,
               acl="private",
               meta_data={},
               allowed_extensions=None,
               overwrite=False):
        """
        To upload file
        :param file:
        :param object_name:
        :param acl:
        :param meta_data:
        :param allowed_extensions:
        :param overwrite:
        :return: StorageObject
        """
        extra = {
            "meta_data": meta_data,
            "acl": acl
        }

        if isinstance(file, FileStorage):
            extension = get_file_extension(file.filename)
        else:
            extension = get_file_extension(file)

        if not object_name:
            if isinstance(file, FileStorage):
                object_name = get_file_name(file.filename)
            else:
                object_name = get_file_name(file)
        object_name = object_name.strip("/").strip()

        if not allowed_extensions:
            allowed_extensions = self.allowed_extensions
        if extension.lower() not in allowed_extensions:
            raise InvalidExtensionError("Invalid file extension")

        if isinstance(self.driver, LocalStorageDriver):
            object_name = secure_filename(object_name)

        if get_file_extension(object_name).strip() == "":
            object_name += "." + extension

        if not overwrite:
            object_name = self._safe_object_name(object_name)

        obj = self.container.upload_object(file_path=file,
                                           object_name=object_name,
                                           extra=extra)
        return StorageObject(obj=obj, cloudstorage=self)

    def object_exists(self, object_name):
        """
        Test if object exists
        :param object_name:
        :return bool:
        """
        try:
            container_name = self.container.name
            self.driver.get_object(container_name, object_name)
            return True
        except ObjectDoesNotExistError:
            return False

    def _safe_object_name(self, object_name):
        """ If the file already exists the file will be renamed to contain a
        short url safe UUID. This will avoid overwtites.
        Arguments
        ---------
        filename : str
            A filename to check if it exists
        Returns
        -------
        str
            A safe filenaem to use when writting the file
        """
        extension = get_file_extension(object_name)
        filename = get_file_name(object_name)
        file_name = filename.strip("." + extension)
        while self.object_exists(object_name):
            uuid = shortuuid.uuid()
            object_name = "%s__%s.%s" % (file_name, uuid, extension)
        return object_name

class StorageObject(object):
    """
    attr:
        name
        size
        hash
        container
        extra
        meta_data
        driver

        download
        delete
    """
    def __init__(self, obj, cloudstorage=None):
        self.obj = obj
        self.cloudstorage = cloudstorage

    def __getattr__(self, item):
        return getattr(self.obj, item)

    def __len__(self):
        return self.size

    @property
    def url(self):
        return self.obj.get_cdn_url()

    @property
    def extension(self):
        return get_file_extension(self.name)

    @property
    def type(self):
        return get_file_extension_type(self.name)

    def exists(self):
        return self.cloudstorage.object_exists(self.name)
