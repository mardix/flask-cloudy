import os

import pytest
from libcloud.storage.base import (StorageDriver,
                                   Container)
from tests import config
from flask_cloudstorage import (get_file_extension,
                                get_file_extension_type,
                                Storage,
                                StorageObject,
                                InvalidExtensionError)

CWD = os.path.dirname(__file__)

# Manipulate
class App(object):
    config = config=dict(
        CLOUDSTORAGE_PROVIDER=config.PROVIDER,
        CLOUDSTORAGE_KEY=config.KEY,
        CLOUDSTORAGE_SECRET=config.SECRET,
        CLOUDSTORAGE_CONTAINER=config.CONTAINER,
        CLOUDSTORAGE_LOCAL_PATH=CWD,
        CLOUDSTORAGE_ALLOWED_EXTENSIONS=[])

def _setup_function():
    pass

def _teardown_function():
    pass

def test_get_file_extension():
    filename = "hello.jpg"
    assert get_file_extension(filename) == "jpg"

def test_get_file_extension_type():
    filename = "hello.mp3"
    assert get_file_extension_type(filename) == "AUDIO"

#---

app = App()

def app_storage():
    return Storage(app=app)

def test_get_driver_class():
    driver = Storage.get_driver_class("S3")
    assert isinstance(driver, type)

def test_driver():
    storage = app_storage()
    assert isinstance(storage.driver, StorageDriver)

def test_container():
    storage = app_storage()
    assert isinstance(storage.container, Container)

def test_set_container():
    storage = app_storage()
    storage.container = config.CONTAINER_2
    assert storage.container.name == config.CONTAINER_2

def test_flask_app():
    storage = app_storage()
    assert isinstance(storage.driver, StorageDriver)

def _test_iter():
    storage = app_storage()
    l = [o for o in storage]
    assert isinstance(l, list)

def test_storage_object_not_exists():
    object_name = "hello.png"
    storage = app_storage()
    assert storage.object_exists(object_name) is False

def test_storage_object():
    object_name = "hello.txt"
    storage = app_storage()
    o = storage.object(object_name)
    assert isinstance(o, StorageObject)

def test_object_type_extension():
    object_name = "hello.jpg"
    storage = app_storage()
    o = storage.object(object_name)
    assert o.type == "IMAGE"
    assert o.extension == "jpg"

def test_object_not_exists():
    object_name = "hello.png"
    storage = app_storage()
    o = storage.object(object_name)
    assert o.exists() is False

def test_storage_upload_invalid():
    storage = app_storage()
    object_name = "my-js/hello.js"
    with pytest.raises(InvalidExtensionError):
        storage.upload(CWD + "/data/hello.js", object_name)

def test_storage_upload_ovewrite():
    storage = app_storage()
    object_name = "my-txt-hello.txt"
    o = storage.upload(CWD + "/data/hello.txt", object_name, overwrite=True)
    assert isinstance(o, StorageObject)
    assert o.name == object_name

def test_storage_upload():
    storage = app_storage()
    object_name = "my-txt-hello2.txt"
    storage.upload(CWD + "/data/hello.txt", object_name)
    o = storage.upload(CWD + "/data/hello.txt", object_name)
    assert isinstance(o, StorageObject)
    assert o.name != object_name