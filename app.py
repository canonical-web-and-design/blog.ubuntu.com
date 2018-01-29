import datetime
import urllib
import flask
import json
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
GROUPBYID = {
    1706: {'slug': 'cloud-and-server', 'name': 'Cloud and server'},
    1666: {'slug': 'internet-of-things', 'name': 'Internet of things'},
    1479: {'slug': 'desktop', 'name': 'Desktop'},
    2100: {'slug': 'canonical-announcements', 'name': 'Canonical announcements'},
    1707: {'slug': 'phone-and-tablet', 'name': 'Phone and tablet'},
}
GROUPBYSLUG = {
    'cloud-and-server': {'id': 1706, 'name': 'Cloud and server'},
    'internet-of-things': {'id': 1666, 'name': 'Internet of things'},
    'desktop': {'id': 1479, 'name': 'Desktop'},
    'canonical-announcements': {'id': 2100, 'name': 'Canonical announcements'},
    'phone-and-tablet': {'id': 1707, 'name': 'Phone and tablet'},
}
CATEGORIESBYID = {
    1172: {'slug': 'case-studies', 'name': 'Case Study'},
    1187: {'slug': 'webinars', 'name': 'Webinar'},
    1189: {'slug': 'news', 'name': 'News'},
    1453: {'slug': 'articles', 'name': 'Article'},
    1485: {'slug': 'whitepapers', 'name': 'Whitepaper'},
    1509: {'slug': 'videos', 'name': 'Video'},
    2497: {'slug': 'tutorials', 'name': 'Tutorial'},
}
CATEGORIESBYSLUG = {
    'all': {'id': None, 'name': 'All'},
    'case-studies': {'id': 1172, 'name': 'Case Study'},
    'webinars': {'id': 1187, 'name': 'Webinar'},
    'news': {'id': 1189, 'name': 'News'},
    'articles': {'id': 1453, 'name': 'Article'},
    'whitepapers': {'id': 1485, 'name': 'Whitepaper'},
    'videos': {'id': 1509, 'name': 'Video'},
    'tutorials': {'id': 2497, 'name': 'Tutorial'},
}
TOPICBYID = {
    1979: {"name": "Big data", "slug": "big-data"},
    1477: {"name": "Cloud", "slug": "cloud"},
    2099: {"name": "Canonical announcements", "slug": "canonical-announcements"},
    1921: {"name": "Desktop", "slug": "desktop"},
    1924: {"name": "Internet of Things", "slug": "internet-of-things"},
    2052: {"name": "People and culture", "slug": "people-and-culture"},
    1340: {"name": "Phone", "slug": "phone"},
    1922: {"name": "Server", "slug": "server"},
    1481: {"name": "Tablet", "slug": "tablet"},
    1482: {"name": "TV", "slug": "tv"},
}
PAGE_TYPE = ""
GROUP = ""

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
cached_session = requests_cache.CachedSession(expire_after=6000)

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

def _get_posts(groups=[], categories=[], tags=[], page=None):
    api_url = '{api_url}/posts?_embed&per_page=12&page={page}'.format(
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
    api_url = '{api_url}/tags?embed&per_page=3&post={post_id}'.format(
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

def _get_tag_details_from_post(post_id):
    api_url = '{api_url}/tags?post={post_id}'.format(
        api_url=API_URL,
        post_id=post_id,
    )
    response = _get_from_cache(api_url)
    tags = json.loads(response.text)
    return tags

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

def _get_category_by_id(category_id):
    global CATEGORIESBYID
    return CATEGORIESBYID[category_id]

def _get_category_by_slug(category_name):
    global CATEGORIESBYSLUG
    return CATEGORIESBYSLUG[category_name]

def _get_group_by_id(group_id):
    global GROUPBYID
    return GROUPBYID[group_id]

def _get_group_by_slug(group_slug):
    global GROUPBYSLUG
    return GROUPBYSLUG[group_slug]

def _get_topic_by_id(topic_id):
    global TOPICBYID
    return TOPICBYID[topic_id]

def _embed_post_data(post):
    if '_embedded' not in post:
        return post
    global PAGE_TYPE
    global GROUP
    embedded = post['_embedded']
    post['author'] = _normalise_user(embedded['author'][0])
    post['category'] = _get_category_by_id(post['categories'][0])
    if PAGE_TYPE == "post":
        post['tags'] = _get_tag_details_from_post(post['id'])
    post['topics'] = _get_topic_by_id(post['topic'][0])
    if GROUP:
        post['groups'] = _get_group_by_id(GROUP)
    else:
        if post['group']:
            post['groups'] = _get_group_by_id(post['group'][0])
    return post

def _normalise_user(user):
    global PAGE_TYPE
    link = user['link']
    path = urlsplit(link).path
    user['relative_link'] = path
    if PAGE_TYPE == "author":
        user['recent_posts'] = _get_user_recent_posts(user['id'])
    return user

def _normalise_posts(posts):
    for post in posts:
        if post['excerpt']['rendered']:
            # replace headings (e.g. h1) to paragraphs
            post['excerpt']['rendered'] = re.sub( r"h\d>", "p>", post['excerpt']['rendered'] )
            # remove images
            post['excerpt']['rendered'] = re.sub( r"<img(.[^>]*)?", "", post['excerpt']['rendered'] )
            # shorten to 250 chars, on a wordbreak and with a ...
            post['excerpt']['rendered'] = textwrap.shorten(post['excerpt']['rendered'], width=250, placeholder="&hellip;")
            # if there is a [...] replace with ...
            post['excerpt']['rendered'] = re.sub( r"\[\&hellip;\]", "&hellip;", post['excerpt']['rendered'] )
        post = _normalise_post(post)
    return posts


def _normalise_post(post):
    link = post['link']
    path = urlsplit(link).path
    post['relative_link'] = path
    post['formatted_date'] = datetime.datetime.strftime(parser.parse(post['date']), "%d %B %Y").lstrip("0").replace(" 0", " ")
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


@app.route('/')
@app.route('/<group>/')
@app.route('/<group>/<category>/')
def group_category(group=[], category='all'):
    groups = []
    categories = []

    global PAGE_TYPE
    PAGE_TYPE = "group"

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

        groups = _get_group_by_slug(group)

        if not groups:
            return flask.render_template(
                '404.html'
            )
        group_details =_get_group_details(group) # read the json file

    global GROUP
    GROUP = groups['id'] if groups else None
    groups_id = [groups['id']] if groups else None

    categories = _get_category_by_slug(category)
    categories_id = [categories['id']] if categories['id'] else None

    page = flask.request.args.get('page')
    posts, metadata = _get_posts(
        groups=groups_id,
        categories=categories_id,
        page=page
    )

    featured_post = _get_featured_post(groups_id)

    webinars = _load_rss_feed('https://www.brighttalk.com/channel/6793/feed/rss')

    if group:
        return flask.render_template(
            'group.html',
            posts=posts,
            group=groups if groups else None,
            group_details=group_details,
            category=category if category else None,
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

    global PAGE_TYPE
    PAGE_TYPE = "topic"

    global GROUP
    GROUP = ''

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

    global PAGE_TYPE
    PAGE_TYPE = "tag"

    response_json = json.loads(response.text)
    if response_json:
        tag = response_json[0]
        page = flask.request.args.get('page')
        posts, metadata = _get_posts(tags=tag['id'], page=page)

        return flask.render_template(
            'tag.html', posts=posts, tag=tag, **metadata
        )
    else:
        return flask.render_template(
            '404.html'
        )


@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<regex("[0-9]{2}"):day>'
    '/<slug>/'
)
def post(year, month, day, slug):
    global PAGE_TYPE
    PAGE_TYPE = "post"
    api_url = ''.join([API_URL, '/posts?_embed&slug=', slug])
    response = _get_from_cache(api_url)
    data = json.loads(response.text)[0]
    data = _normalise_post(data)
    data['related_posts'] = _get_related_posts(data)
    return flask.render_template('post.html', post=data)


@app.route('/author/<slug>/')
def user(slug):
    global PAGE_TYPE
    PAGE_TYPE = "author"
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
