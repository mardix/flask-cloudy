
from flask import Flask, request, render_template, redirect, abort, url_for
from flask_cloudy import Storage

app = Flask(__name__)

app.config.update({
    "STORAGE_PROVIDER": "LOCAL",
    "STORAGE_CONTAINER": "./data",
    "STORAGE_KEY": "",
    "STORAGE_SECRET": "",
    "STORAGE_SERVER": True
})

storage = Storage()
storage.init_app(app)

@app.route("/")
def index():

    return render_template("index.html", storage=storage)

@app.route("/view/<path:object_name>")
def view(object_name):
    obj = storage.get(object_name)
    print obj.name
    return render_template("view.html", obj=obj)

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    my_object = storage.upload(file)
    return redirect(url_for("view", object_name=my_object.name))


if __name__ == "__main__":
    app.run(debug=True, port=5000)