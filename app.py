import datetime
import urllib
import flask
import json
import humanize
import requests
import requests_cache
import re
import textwrap
from dateutil import parser
from flask import url_for
from flask import request
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlsplit
from werkzeug.routing import BaseConverter
from lib.get_feeds import (
    get_rss_feed_content
)


INSIGHTS_URL = 'https://insights.ubuntu.com'
API_URL = INSIGHTS_URL + '/wp-json/wp/v2'


app = flask.Flask(__name__)


# Setup session to retry requests 5 times
uncached_session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=0.1,
    status_forcelist=[500, 502, 503, 504]
)
uncached_session.mount(
    'https://api.snapcraft.io',
    HTTPAdapter(max_retries=retries)
)

# The cache expires after 10 minutes
cached_session = requests_cache.CachedSession(expire_after=600)

# Requests should timeout after 2 seconds in total
request_timeout = 10


def _get_from_cache(url, json=None):
    """
    Retrieve the response from the requests cache.
    If the cache has expired then it will attempt to update the cache.
    If it gets an error, it will use the cached response, if it exists.
    """

    request_error = False

    method = "POST" if json else "GET"

    request = cached_session.prepare_request(
        requests.Request(
            method=method,
            url=url,
            json=json
        )
    )

    cache_key = cached_session.cache.create_key(request)
    response, timestamp = cached_session.cache.get_response_and_time(
        cache_key
    )

    if response:
        age = datetime.datetime.utcnow() - timestamp

        if age > cached_session._cache_expire_after:
            try:
                new_response = uncached_session.send(
                    request,
                    timeout=request_timeout
                )
                if response.status_code >= 500:
                    new_response.raise_for_status()
            except:
                request_error = True
            else:
                response = new_response
    else:
        response = cached_session.send(request)

    response.old_data_from_error = request_error

    return response


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app.url_map.converters['regex'] = RegexConverter

def _get_categories_by_slug(slugs=[]):
    if slugs:
        if isinstance(slugs, list):
            slugs = ','.join(slugs)
    api_url = '{api_url}/categories?slug={slug}'.format(
        api_url=API_URL,
        slug=slugs,
    )
    response = _get_from_cache(api_url)
    categories = json.loads(response.text)
    return categories

def _get_groups_by_slug(slugs=[]):
    if slugs:
        if isinstance(slugs, list):
            slugs = ','.join(slugs)
    api_url = '{api_url}/group?slug={slug}'.format(
        api_url=API_URL,
        slug=slugs,
    )
    response = _get_from_cache(api_url)
    groups = json.loads(response.text)
    return groups


def _get_posts(groups=[], categories=[], tags=[], page=None):
    api_url = '{api_url}/posts?_embed&page={page}'.format(
        api_url=API_URL,
        page=str(page or 1),
    )

    if groups:
        groups = ','.join(str(group) for group in groups)
        api_url = ''.join([api_url, '&group=', groups])

    if categories:
        categories = ','.join(str(category) for category in categories)
        api_url = ''.join([api_url, '&categories=', categories])

    if tags:
        if isinstance(tags, list):
            tags = ','.join(str(tag) for tag in tags)
        api_url = ''.join([api_url, '&tags=', str(tags)])

    response = _get_from_cache(api_url)

    headers = response.headers
    metadata = {
        'current_page': page or 1,
        'total_pages': headers.get('X-WP-TotalPages'),
        'total_posts': headers.get('X-WP-Total'),
    }

    posts = _normalise_posts(json.loads(response.text))

    return posts, metadata


def _get_related_posts(post):
    api_url = '{api_url}/tags?embed&post={post_id}'.format(
        api_url=API_URL,
        post_id=post['id'],
    )
    response = _get_from_cache(api_url)
    tags = json.loads(response.text)

    tag_ids = [tag['id'] for tag in tags]
    posts, meta = _get_posts(tags=tag_ids)
    posts = _normalise_posts(posts)
    return posts


def _get_user_recent_posts(user_id, limit=5):
    api_url = '{api_url}/posts?embed&author={user_id}&per_page={limit}'.format(
        api_url=API_URL,
        user_id=user_id,
        limit=limit,
    )
    response = _get_from_cache(api_url)
    posts = _normalise_posts(json.loads(response.text))

    return posts

def _get_category_from_post(post_id):
    api_url = '{api_url}/categories?post={post_id}'.format(
        api_url=API_URL,
        post_id=post_id,
    )
    response = _get_from_cache(api_url)
    category = json.loads(response.text)[0]['slug']
    return category

def _get_tag_details_from_post(post_id):
    api_url = '{api_url}/tags?post={post_id}'.format(
        api_url=API_URL,
        post_id=post_id,
    )
    response = _get_from_cache(api_url)
    tags = json.loads(response.text)
    return tags


def _get_topic_details_from_post(post_id):
    api_url = '{api_url}/topic?post={post_id}'.format(
        api_url=API_URL,
        post_id=post_id,
    )
    response = _get_from_cache(api_url)
    topics = json.loads(response.text)
    return topics


def _get_featured_post(groups=[], categories=[], per_page=1):
    api_url = '{api_url}/posts?_embed&sticky=true&per_page={per_page}'.format(
        api_url=API_URL,
        per_page=per_page
    )

    if groups:
        groups = ','.join(str(group) for group in groups)
        api_url = ''.join([api_url, '&group=', groups])

    if categories:
        categories = ','.join(str(category) for category in categories)
        api_url = ''.join([api_url, '&categories=', categories])

    response = _get_from_cache(api_url)
    posts = _normalise_posts(json.loads(response.text))

    return posts[0] if posts else None


def _embed_post_data(post):
    if '_embedded' not in post:
        return post
    embedded = post['_embedded']
    post['author'] = _normalise_user(embedded['author'][0])
    post['category'] = _get_category_from_post(post['id'])
    post['tags'] = _get_tag_details_from_post(post['id'])
    post['topics'] = _get_topic_details_from_post(post['id'])
    return post


def _normalise_user(user):
    link = user['link']
    path = urlsplit(link).path
    user['relative_link'] = path
    user['recent_posts'] = _get_user_recent_posts(user['id'])
    return user


def _normalise_posts(posts):
    for post in posts:
        if post['excerpt']['rendered']:
            post['excerpt']['rendered'] = textwrap.shorten(post['excerpt']['rendered'], width=250, placeholder="&hellip;")
            post['excerpt']['rendered'] = re.sub( r"\[\&hellip;\]", "&hellip;", post['excerpt']['rendered'] )
            post['excerpt']['rendered'] = re.sub( r"h\d>", "p>", post['excerpt']['rendered'] )
        post = _normalise_post(post)
    return posts


def _normalise_post(post):
    link = post['link']
    path = urlsplit(link).path
    post['relative_link'] = path
    post['formatted_date'] = humanize.naturaldate(
        parser.parse(post['date'])
    )
    post = _embed_post_data(post)
    return post

def _get_group_details(slug):
    with open('data/groups.json') as file:
        groups = json.load(file)

    for group in groups:
        if group['slug'] == slug:
            return group

def _get_topic_details(slug):
    with open('data/topics.json') as file:
        topics = json.load(file)

    for topic in topics:
        if topic['slug'] == slug:
            return topic

def _load_rss_feed(url, limit=5):
    feed_content = get_rss_feed_content(url, limit=limit)
    return feed_content

def _normalise_post(post):
    link = post['link']
    path = urlsplit(link).path
    post['relative_link'] = path
    post['formatted_date'] = humanize.naturaldate(
        parser.parse(post['date'])
    )
    post = _embed_post_data(post)
    return post

@app.route('/')
@app.route('/<group>/')
@app.route('/<group>/<category>/')
def group_category(group=[], category='all'):
    groups = []
    categories = []

    search = request.args.get('search')

    if search:
        result = {}
        api_url = ''.join([API_URL, '/posts?_embed&search=', search])
        response = _get_from_cache(api_url)
        posts = _normalise_posts(json.loads(response.text))
        result["posts"] = posts
        result["count"] = len(posts)
        result["query"] = search
        return flask.render_template('search.html', result=result)
    if group:
        if group == 'press-centre':
            group = 'canonical-announcements'

        groups = _get_groups_by_slug(slugs=group)
        if not groups:
            return flask.render_template(
                '404.html'
            )
        group_details =_get_group_details(group)

        categories = _get_categories_by_slug(slugs=category)
        if not categories and category != 'all':
            return flask.redirect(flask.url_for('group_category', group=group, category='all'))

    groups_id = [str(group['id']) for group in groups]
    categories_id = [str(category['id']) for category in categories]

    page = flask.request.args.get('page')
    posts, metadata = _get_posts(
        groups=groups_id,
        categories=categories_id if categories_id else None,
        page=page
    )

    featured_post = _get_featured_post(groups_id)

    webinars = _load_rss_feed('https://www.brighttalk.com/channel/6793/feed/rss')

    if group:
        return flask.render_template(
            'group.html',
            posts=posts,
            group=groups[0] if groups else None,
            group_details=group_details,
            category=categories[0] if categories else None,
            featured_post=featured_post,
            **metadata
        )
    else:
        return flask.render_template(
            'index.html',
            posts=posts,
            featured_post=featured_post,
            webinars=webinars,
            **metadata
        )


@app.route('/topics/<slug>/')
def topic_name(slug):
    topic = _get_topic_details(slug)

    if topic:
        api_url = ''.join([API_URL, '/tags?slug=', topic['slug']])
        response = _get_from_cache(api_url)

        response_json = json.loads(response.text)
        if response_json:
            tag = response_json[0]
            page = flask.request.args.get('page')
            posts, metadata = _get_posts(tags=tag['id'], page=page)
        else:
            return flask.render_template(
                '404.html'
            )

        return flask.render_template(
            'topics.html', topic=topic, posts=posts, tag=tag, **metadata
        )
    else:
        return flask.render_template(
            '404.html'
        )

@app.route('/tag/<slug>/')
def tag_index(slug):
    api_url = ''.join([API_URL, '/tags?slug=', slug])
    response = _get_from_cache(api_url)

    response_json = json.loads(response.text)
    if response_json:
        tag = response_json[0]
        page = flask.request.args.get('page')
        posts, metadata = _get_posts(tags=tag['id'], page=page)

        return flask.render_template(
            'tag.html', posts=posts, tag=tag, **metadata
        )
    else:
        tag = {
            "id": -1,
            "name": slug
        }

        return flask.render_template(
            'tag.html', posts=[], tag=tag, **{}
        ), 404


@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<regex("[0-9]{2}"):day>'
    '/<slug>/'
)
def post(year, month, day, slug):
    api_url = ''.join([API_URL, '/posts?_embed&slug=', slug])
    response = _get_from_cache(api_url)
    data = json.loads(response.text)[0]
    data = _normalise_post(data)
    data['related_posts'] = _get_related_posts(data)
    return flask.render_template('post.html', post=data)


@app.route('/author/<slug>/')
def user(slug):
    api_url = ''.join([API_URL, '/users?_embed&slug=', slug])
    response = _get_from_cache(api_url)
    data = json.loads(response.text)[0]
    data = _normalise_user(data)
    return flask.render_template('author.html', author=data)


@app.route('/admin/')
@app.route('/feed/')
@app.route('/wp-content/')
@app.route('/wp-includes/')
@app.route('/wp-login.php/')
def redirect_wordpress_login():
    path = flask.request.path
    if (flask.request.args):
        path = '?'.join([path, urllib.parse.urlencode(flask.request.args)])

    return flask.redirect(INSIGHTS_URL + path)

@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404

@app.errorhandler(410)
def page_not_found(e):
    return flask.render_template('410.html'), 410

@app.errorhandler(500)
def page_not_found(e):
    return flask.render_template('500.html'), 500
