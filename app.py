import flask
import json
import os

from urllib.parse import urlsplit


INSIGHTS_URL = 'https://insights.ubuntu.com/wp-json/wp/v2'


app = flask.Flask(__name__)


def _embed_post_data(post):
    if '_embedded' not in post:
        return post
    embedded = post['_embedded']
    post['author'] = embedded['author']
    print(post['author'])
    return post


def _normalise_post(post):
    link = post['link']
    path = urlsplit(link).path
    post['relative_link'] = path
    post = _embed_post_data(post)
    return post


@app.route("/")
def index():
    SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
    json_path = os.path.join(SITE_ROOT, "data", "posts.json")
    with open(json_path) as json_data:
        data = json.load(json_data)
    return flask.render_template('index.html', posts=data)


# @app.route('/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>/<regex("[0-9]{2}"):day>/<slug>/')
# def post(year, month, day, slug):
#     return flask.render_template('index.html')


@app.route('/desktop/')
def index_dev():
    SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
    json_path = os.path.join(SITE_ROOT, "data", "posts.json")
    with open(json_path) as json_data:
        data = json.load(json_data)
    for post in data:
        post = _normalise_post(post)
    return flask.render_template('index.html', posts=data)


@app.route('/2017/09/19/results-of-the-ubuntu-desktop-applications-survey/')
def post_dev():
    SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
    json_path = os.path.join(SITE_ROOT, "data", "post.json")
    with open(json_path) as json_data:
        data = json.load(json_data)
    data = _normalise_post(data)
    return flask.render_template('post.html', post=data)
