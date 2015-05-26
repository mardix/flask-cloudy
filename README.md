# Flask-CloudStorage

A wrapper around Apache-Libcloud to upload and save files on cloud storage
providers such as: AWS S3, Google Storage, Microsoft Azure, Rackspace Cloudfiles,
and even on local storage through a Flask application. 
(It can be used as standalone)

For local file storage, it provides a flask endpoint to access the files

Supported storage:

- AWS S3
- Google Storage
- Microsoft Azure
- Rackspace CloudFiles
- Local (for local file system)

## Install

    pip install flask-cloudstorage


### Example of uploading a file

    from flask import Flask, request
    from flask_cloudstorage import Storage
    
    app = Flask(__name__)
    
    storage = Storage(app=app)
    
    @route("/upload", methods=["POST", "GET"]):
    def upload():
        if request.method == "POST":
            my_upload = storage.upload(request.file.get("file"))
            name = my_upload.name
            size = my_upload.size
            url = my_upload.get_url()
            return url
        
---

(c) 2015 Mardix