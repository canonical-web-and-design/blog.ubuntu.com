import flask
import json
import os


app = flask.Flask(__name__)


@app.route("/")
def index():
    return flask.render_template('index.html')


# @app.route('/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>/<regex("[0-9]{2}"):day>/<slug>/')
# def post(year, month, day, slug):
#     return flask.render_template('index.html')


@app.route('/desktop/')
def index_dev():
    SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
    json_path = os.path.join(SITE_ROOT, "data", "posts.json")
    with open(json_path) as json_data:
        data = json.load(json_data)
        print(data)
    return flask.render_template('index.html', posts=data)


@app.route('/2017/09/19/results-of-the-ubuntu-desktop-applications-survey/')
def post_dev():
    SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
    json_path = os.path.join(SITE_ROOT, "data", "post.json")
    with open(json_path) as json_data:
        data = json.load(json_data)
        print(data)
    return flask.render_template('post.html', post=data)
