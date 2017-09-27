import flask
import json
import os
import requests

from urllib.parse import urlsplit
from werkzeug.routing import BaseConverter


INSIGHTS_URL = 'https://insights.ubuntu.com/wp-json/wp/v2'


app = flask.Flask(__name__)


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app.url_map.converters['regex'] = RegexConverter


def _get_posts(category=None, limit=10):
    api_url = '{api_url}/posts?embed&per_page={limit}'.format(
        api_url=INSIGHTS_URL,
        limit=limit,
    )
    response = requests.get(api_url)
    posts = json.loads(response.text)
    for post in posts:
        post = _normalise_post(post)
    return posts


def _get_user_recent_posts(user_id, limit=5):
    api_url = '{api_url}/posts?embed&author={user_id}&per_page={limit}'.format(
        api_url=INSIGHTS_URL,
        user_id=user_id,
        limit=limit,
    )
    response = requests.get(api_url)
    posts = json.loads(response.text)
    for post in posts:
        post = _normalise_post(post)
    return posts


def _embed_post_data(post):
    if '_embedded' not in post:
        return post
    embedded = post['_embedded']
    post['author'] = _normalise_user(embedded['author'][0])
    return post


def _normalise_user(user):
    link = user['link']
    path = urlsplit(link).path
    user['relative_link'] = path
    user['recent_posts'] = _get_user_recent_posts(user['id'])
    return user


def _normalise_post(post):
    link = post['link']
    path = urlsplit(link).path
    post['relative_link'] = path
    post = _embed_post_data(post)
    return post


@app.route("/")
def index():
    posts = _get_posts()
    return flask.render_template('index.html', posts=posts, category=None)


@app.route("/<category>/")
def category(category):
    posts = _get_posts(category=category)
    return flask.render_template('index.html', posts=posts, category=category)


@app.route('/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>/<regex("[0-9]{2}"):day>/<slug>/')
def post(year, month, day, slug):
    api_url = ''.join([INSIGHTS_URL, '/posts?_embed&slug=', slug])
    response = requests.get(api_url)
    data = json.loads(response.text)[0]
    data = _normalise_post(data)
    return flask.render_template('post.html', post=data)


@app.route('/author/<slug>/')
def user(slug):
    api_url = ''.join([INSIGHTS_URL, '/users?_embed&slug=', slug])
    response = requests.get(api_url)
    data = json.loads(response.text)[0]
    data = _normalise_user(data)
    return flask.render_template('author.html', author=data)
