# Flask-Cloudy


## About

A Flask extension to **access, upload, download, save and delete** files on cloud storage providers such as: 
AWS S3, Google Storage, Microsoft Azure, Rackspace Cloudfiles, and even Local file system.

For local file storage, it also provides a flask endpoint to access the files.
 
 
Version: 0.13.*

---

##TLDR; Quick Example

	from flask import Flask, request
	from flask_cloudy import Storage
	
	app = Flask(__name__)
	
	# Update the config 
	app.config.update({
		"STORAGE_PROVIDER": "LOCAL", # Can also be S3, GOOGLE_STORAGE, etc... 
		"STORAGE_KEY": "",
		"STORAGE_SECRET": "",
		"STORAGE_CONTAINER": "./",  # a directory path for local, bucket name of cloud
		"STORAGE_SERVER": True,
		"STORAGE_SERVER_URL": "/files" # The url endpoint to access files on LOCAL provider
	})
	
	# Setup storage
	storage = Storage()
	storage.init_app(app) 
	
    @app.route("/upload", methods=["POST", "GET"]):
    def upload():
        if request.method == "POST":
        	file = request.files.get("file")
            my_upload = storage.upload(file)
            
            # some useful properties
            name = my_upload.name
            extension = my_upload.extension
            size = my_upload.size
            url = my_upload.url
            
            return url
        
    # Pretending the file uploaded is "my-picture.jpg"    
	# it will return a url in the format: http://domain.com/files/my-picture.jpg


	# A download endpoint, to download the file
    @app.route("/download/<path:object_name>"):
    def download(object_name):
        my_object = storage.get(object_name)
        if my_object:
        	download_url = my_object.download()
        	return download_url
        else:	
        	abort(404, "File doesn't exist")

---        
       
Go to the "example" directory to get a workable flask-cloud example


--- 
  
  
### Features:

- Browse files

- Upload files

- Download files

- Delete files

- Serve files via http


### Supported storage:

- AWS S3

- Google Storage

- Microsoft Azure

- Rackspace CloudFiles

- Local (for local file system)


**Dependecies:** (They will be installed upon setup)

- Flask

- Apache-Libcloud 
 
---

## Install & Config

    pip install flask-cloudy

---

(To use it as standalone, refer to API documentaion below)

## Config for Flask

Within your Flask application's settings you can provide the following settings to control
the behavior of Flask-Cloudy
 

**- STORAGE_PROVIDER** (str) 

- LOCAL
- S3
- S3_US_WEST
- S3_US_WEST_OREGON
- S3_EU_WEST
- S3_AP_SOUTHEAST
- S3_AP_NORTHEAST
- GOOGLE_STORAGE
- AZURE_BLOBS
- CLOUDFILES


**- STORAGE_KEY** (str)

The access key of the cloud storage provider

None for LOCAL

**- STORAGE_SECRET** (str)

The access secret  key of the cloud storage provider

None for LOCAL

**- STORAGE_CONTAINER** (str)

The *BUCKET NAME* for cloud storage providers

For *LOCAL* provider, this is the local directory path 


**STORAGE_ALLOWED_EXTENSIONS** (list)

List of all extensions to allow

Example: ["png", "jpg", "jpeg", "mp3"]

**STORAGE_SERVER** (bool)

For *LOCAL* provider only. 

True to expose the files in the container so they can be accessed

Default: *True*

**STORAGE_SERVER_URL** (str)

For *LOCAL* provider only.

The endpoint to access the files from the local storage. 

Default: */files*

---

## API Documention

Flask-Cloudy is a wrapper around Apache-Libcloud, the Storage class gives you access to Driver and Container of Apache-Libcloud.

*Lexicon:*

Object: A file or a file path. 

Container: The main directory, or a bucket name containing all the objects

Provider: The method 

Storage: 

### flask_cloudy.Storage

The **Storage** class allows you to access, upload, get an object from the Storage. 

##### Storage(provider, key=None, secret=None, container=None, allowed_extensions=None)

- provider: the storage provider:

    - LOCAL
    - S3
    - S3_US_WEST
    - S3_US_WEST_OREGON
    - S3_EU_WEST
    - S3_AP_SOUTHEAST
    - S3_AP_NORTHEAST
    - GOOGLE_STORAGE
    - AZURE_BLOBS
    - CLOUDFILES

- key: The access key of the cloud storage. None when provider is LOCAL

- secret: The secret access key of the cloud storage. None when provider is LOCAL

- container: 

     - For cloud storage, use the **BUCKET NAME** 
     
     - For LOCAL provider, it's the directory path where to access the files 
     
- allowed_extensions: List of extensions to upload to upload


##### Storage.init_app(app)

To initiate the Storage via Flask config.

It will also setup a server endpoint when STORAGE_PROVIDER == LOCAL

	from flask import Flask, request
	from flask_cloudy import Storage
	
	app = Flask(__name__)
	
	# Update the config 
	app.config.update({
		"STORAGE_PROVIDER": "LOCAL", # Can also be S3, GOOGLE_STORAGE, etc... 
		"STORAGE_KEY": "",
		"STORAGE_SECRET": "",
		"STORAGE_CONTAINER": "./",  # a directory path for local, bucket name of cloud
		"STORAGE_SERVER": True,
		"STORAGE_SERVER_URL": "/files"
	})
	
	# Setup storage
	storage = new Storage()
	storage.init_app(app) 
	
    @app.route("/upload", methods=["POST", "GET"]):
    def upload():
        if request.method == "POST":
        	file = request.files.get("file")
            my_upload = storage.upload(file)
            
            # some useful properties
            name = my_upload.name
            extension = my_upload.extension
            size = my_upload.size
            url = my_upload.url
            
            return url
        
    # Pretending the file uploaded is "my-picture.jpg"    
	# it will return a url in the format: http://domain.com/files/my-picture.jpg
	


##### Storage.get(object_name)

Get an object in the storage by name, relative to the container.

It will return an instance of **flask_cloudy.Object**

- object_name: The name of the object.

Some valid object names, they can contains slashes to indicate it's a directory


    - file.txt
    
    - my_dir/file.txt
    
    - my_dir/sub_dir/file.txt

.

	storage = Storage(provider, key, secret, container)
	object_name = "hello.txt"
	my_object = storage.get(object_name)
	
	

##### Storage.upload(file, name=None, prefix=None, allowed_extesion=[], overwrite=Flase, public=False)

To save or upload a file in the container

- file: the string of the file location or a file object

- name: to give the file a new name

- prefix: a name to add in front of the file name. Add a slash at the end of 
prefix to make it a directory otherwise it will just append it to the name

- allowed_extensions: list of extensions

- overwrite: If True it will overwrite existing files, otherwise it will add a uuid in the file name to make it unique

- public: Bool - To set the **acl** to *public-read* when True, *private* when False

.

	storage = Storage(provider, key, secret, container)
	my_file = "my_dir/readme.md"
	
		
**1) This example will upload the file, an assign the object the name of the file**
	
	storage.upload(my_file)	
	
	
**2) This example will upload the file, an assign the object the name of the file**
	
	storage.upload(my_file, name="new_readme")
	
The uploaded file will be named: **new_readme.md**
	
	
**3) Put the uploaded file under a different location using `prefix`**
	
	
	storage.upload(my_file, name="new_readme", prefix="my_dir/")

	
now the filename becomes **my_dir/new_readme.md**

On LOCAL it will create the directory *my_dir* if it doesn't exist. 

	
	storage.upload(my_file, name="new_readme", prefix="my_new_path-")

	
now the filename becomes **my_new_path-new_readme.md**
 

**4a.) Public upload**

	storage.upload(my_file, public=True)
	
	
**4b.) Private upload**

	storage.upload(my_file, public=False)


##### Storage.create(object_name, size=0, hash=None, extra=None, metda_data=None)

Explicitly create an object that may exist already. Usually, when paramameters (name, size, hash, etc...) are already saved, let's say in the database, and you want Storage to manipulate the file. 

	storage = Storage(provider, key, secret, container)
	existing_name = "holla.txt"
	existing_size = "8000" # in bytes
	new_object = storage.create(object_name=existing_name, size=existing_size)
	
	# Now I can do
	url = new_object.url 
	size = len(new_object)

*It's Pythonic!!!*

##### Iterate through all the objects in the container

Each object is an instance on **flask_cloudy.Object**

	storage = Storage(provider, key, secret, container)
	for obj in storage:
		print(obj.name)

##### Get the total objects in the container

	storage = Storage(provider, key, secret, container)
	total_items = len(storage)

##### Check to see if an object exists in the container

	storage = Storage(provider, key, secret, container)
	my_file = "hello.txt"
	
	if my_file in storage:
		print("File is in the storage")

---


### flask_cloudy.Object

The class **Object** is an entity of an object in the container.

Usually, you will get a cloud object by accessing an object in the container.

	storage = Storage(provider, key, secret, container)
	my_object = storage.get("my_object.txt")
	
Properties:
	
##### Object.name 

The name of the object


##### Object.size

The size in bytes of the object


##### Object.extension

The extension of the object


##### Object.url

Return the url of the object

On LOCAL, it will return the url without the domain name ( ie: /files/my-file.jpg )

For cloud providers it will return the full url

##### Object.full_url 

Returns the full url of the object

Specially for LOCAL provider, it will return the url with the domain.

For cloud providers, it will return the full url just like **Object.url**


##### Object.secure_url 

Return a secured url, with **https://** 


##### Object.path

The path of the object relative to the container
 

##### Object.provider_name 

The provider name: ie: Local, S3,...


##### Object.type 

The type of the object, ie: IMAGE, AUDIO, TEXT,... OTHER


Methods:

##### Object.save_to(destination, name=None, overwrite=False, delete_on_failure=True)

To save the object to a local path 

- destination: The directory to save the object to

- name: To rename the file in the local directory. Do not put the extension of the file, it will append automatically

- overwrite: bool - To overwrite the file if it exists

- delete_on_failure: bool - To delete the file it fails to save

.

	storage = Storage(provider, key, secret, container)
	my_object = storage.get("my_object.txt")
	my_new_path = "/my/new/path"
	my_new_file = my_object.save_to(my_new_path)
	
	print(my_new_file) # Will print -> /my/new/path/my_object.txt


##### Object.download_url(timeout=60, name=None)

Return a URL that triggers the browser download of the file. On cloud providers it will return a signed url.

- timeout: int - The time in seconds to give access to the url

- name: str - for LOCAL only, to rename the file being downloaded

.

	storage = Storage(provider, key, secret, container)
	my_object = storage.get("my_object.txt")
	download_url = my_object.download_url()	
	
	# or with flask

    @app.route("/download/<path:object_name>"):
    def download(object_name):
        my_object = storage.get(object_name)
        if my_object:
        	download_url = my_object.download_url()
        	return redirect(download_url)
        else:	
        	abort(404, "File doesn't exist")
            
---

I hope you find this library useful, enjoy!


Mardix :) 

---

License: MIT - Copyright 2015 Mardix

