import os
import pytest
from libcloud.storage.base import (StorageDriver, Container)
from flask_cloudy import (get_file_extension,
                            get_file_extension_type,
                            get_file_name,
                            get_driver_class,
                            get_provider_name,
                            Storage,
                            Object,
                            InvalidExtensionError)
from tests import config

CWD = os.path.dirname(__file__)

CONTAINER = "%s/%s" % (CWD, config.CONTAINER) if config.PROVIDER == "LOCAL" else config.CONTAINER
CONTAINER2 = "%s/%s" % (CWD, config.CONTAINER2) if config.PROVIDER == "LOCAL" else config.CONTAINER2

class App(object):
    config = dict(
        STORAGE_PROVIDER=config.PROVIDER,
        STORAGE_KEY=config.KEY,
        STORAGE_SECRET=config.SECRET,
        STORAGE_CONTAINER=CONTAINER,
        STORAGE_SERVER=False,
        STORAGE_ALLOWED_EXTENSIONS=[])


def test_get_file_extension():
    filename = "hello.jpg"
    assert get_file_extension(filename) == "jpg"

def test_get_file_extension_type():
    filename = "hello.mp3"
    assert get_file_extension_type(filename) == "AUDIO"

def test_get_file_name():
    filename = "/dir1/dir2/dir3/hello.jpg"
    assert get_file_name(filename) == "hello.jpg"

def test_get_provider_name():
    class GoogleStorageDriver(object):
        pass
    driver = GoogleStorageDriver()
    assert get_provider_name(driver) == "google_storage"

#---

app = App()

def app_storage():
    return Storage(app=App())

def test_get_driver_class():
    driver = get_driver_class("S3")
    assert isinstance(driver, type)

def test_driver():
    storage = app_storage()
    assert isinstance(storage.driver, StorageDriver)

def test_container():
    storage = app_storage()
    assert isinstance(storage.container, Container)

def test_flask_app():
    storage = app_storage()
    assert isinstance(storage.driver, StorageDriver)

def test_iter():
    storage = app_storage()
    l = [o for o in storage]
    assert isinstance(l, list)

def test_storage_object_not_exists():
    object_name = "hello.png"
    storage = app_storage()
    assert object_name not in storage

def test_storage_object():
    object_name = "hello.txt"
    storage = app_storage()
    o = storage.create(object_name)
    assert isinstance(o, Object)

def test_object_type_extension():
    object_name = "hello.jpg"
    storage = app_storage()
    o = storage.create(object_name)
    assert o.type == "IMAGE"
    assert o.extension == "jpg"

def test_object_provider_name():
    object_name = "hello.jpg"
    storage = app_storage()
    o = storage.create(object_name)
    assert o.provider_name == config.PROVIDER.lower()

def test_object_object_path():
    object_name = "hello.jpg"
    storage = app_storage()
    o = storage.create(object_name)
    p = "%s/%s" % (o.container.name, o.name)
    assert o.path.endswith(p)

def test_storage_upload_invalid():
    storage = app_storage()
    object_name = "my-js/hello.js"
    with pytest.raises(InvalidExtensionError):
        storage.upload(CWD + "/data/hello.js", name=object_name)

def test_storage_upload_ovewrite():
    storage = app_storage()
    object_name = "my-txt-hello.txt"
    o = storage.upload(CWD + "/data/hello.txt", name=object_name, overwrite=True)
    assert isinstance(o, Object)
    assert o.name == object_name

def test_storage_get():
    storage = app_storage()
    object_name = "my-txt-helloIII.txt"
    o = storage.upload(CWD + "/data/hello.txt", name=object_name, overwrite=True)
    o2 = storage.get(o.name)
    assert isinstance(o2, Object)

def test_storage_get_none():
    storage = app_storage()
    o2 = storage.get("idonexist")
    assert o2 is None

def test_storage_upload():
    storage = app_storage()
    object_name = "my-txt-hello2.txt"
    storage.upload(CWD + "/data/hello.txt", name=object_name)
    o = storage.upload(CWD + "/data/hello.txt", name=object_name)
    assert isinstance(o, Object)
    assert o.name != object_name

def test_storage_upload_use_filename_name():
    storage = app_storage()
    object_name = "hello.js"
    o = storage.upload(CWD + "/data/hello.js", overwrite=True, allowed_extensions=["js"])
    assert o.name == object_name

def test_storage_upload_append_extension():
    storage = app_storage()
    object_name = "my-txt-hello-hello"
    o = storage.upload(CWD + "/data/hello.txt", object_name, overwrite=True)
    assert get_file_extension(o.name) == "txt"

def test_storage_upload_with_prefix():
    storage = app_storage()
    object_name = "my-txt-hello-hello"
    prefix = "dir1/dir2/dir3/"
    full_name = "%s%s.%s" % (prefix, object_name, "txt")
    o = storage.upload(CWD + "/data/hello.txt", name=object_name, prefix=prefix, overwrite=True)
    assert full_name in storage
    assert o.name == full_name


def test_save_to():
    storage = app_storage()
    object_name = "my-txt-hello-to-save.txt"
    o = storage.upload(CWD + "/data/hello.txt", name=object_name)
    file = o.save_to(CWD + "/data", overwrite=True)
    file2 = o.save_to(CWD + "/data", name="my_new_file", overwrite=True)
    assert os.path.isfile(file)
    assert file2 == CWD + "/data/my_new_file.txt"

def test_delete():
    storage = app_storage()
    object_name = "my-txt-hello-to-delete.txt"
    o = storage.upload(CWD + "/data/hello.txt", name=object_name)
    assert object_name in storage
    o.delete()
    assert object_name not in storage

def test_use():
    storage = app_storage()
    object_name = "my-txt-hello-to-save-with-use.txt"
    f = CWD + "/data/hello.txt"
    with storage.use(CONTAINER2) as s2:
        assert isinstance(s2.container, Container)
        o = s2.upload(f, "hello.txt")
        assert isinstance(o, Object)
    o1 = storage.upload(f, name=object_name)
    assert isinstance(o1, Object)
    assert o1.name == object_name

def test_werkzeug_upload():
    try:
        import werkzeug
    except ImportError:
        return
    storage = app_storage()
    object_name = "my-txt-hello.txt"
    filepath = CWD + "/data/hello.txt"
    file = None
    with open(filepath, 'rb') as fp:
        file = werkzeug.datastructures.FileStorage(fp)
        file.filename = object_name
        o = storage.upload(file, overwrite=True)
        assert isinstance(o, Object)
        assert o.name == object_name

