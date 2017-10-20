import datetime
import flask
import json
import humanize
import requests
import requests_cache
from dateutil import parser
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlsplit
from werkzeug.routing import BaseConverter


INSIGHTS_URL = 'https://insights.ubuntu.com/wp-json/wp/v2'


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


def _get_groups_by_slug(slugs=[]):
    if slugs:
        if isinstance(slugs, list):
            slugs = ','.join(slugs)
    api_url = '{api_url}/group?slug={slug}'.format(
        api_url=INSIGHTS_URL,
        slug=slugs,
    )
    response = _get_from_cache(api_url)
    groups = json.loads(response.text)
    return groups


def _get_posts(groups=[], tags=[], page=None):
    api_url = '{api_url}/posts?_embed&page={page}'.format(
        api_url=INSIGHTS_URL,
        page=str(page or 1),
    )

    if groups:
        groups = ','.join(str(group) for group in groups)
        api_url = ''.join([api_url, '&group=', groups])

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
        api_url=INSIGHTS_URL,
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
        api_url=INSIGHTS_URL,
        user_id=user_id,
        limit=limit,
    )
    response = _get_from_cache(api_url)
    posts = _normalise_posts(json.loads(response.text))

    return posts


def _get_tag_details_from_post(post_id):
    api_url = '{api_url}/tags?post={post_id}'.format(
        api_url=INSIGHTS_URL,
        post_id=post_id,
    )
    response = _get_from_cache(api_url)
    tags = json.loads(response.text)
    return tags


def _get_topic_details_from_post(post_id):
    api_url = '{api_url}/topic?post={post_id}'.format(
        api_url=INSIGHTS_URL,
        post_id=post_id,
    )
    response = _get_from_cache(api_url)
    topics = json.loads(response.text)
    return topics


def _get_featured_post(groups=[], per_page=1):
    api_url = '{api_url}/posts?embed&sticky=true&per_page={per_page}'.format(
        api_url=INSIGHTS_URL,
        per_page=per_page
    )

    if groups:
        groups = ','.join(str(group) for group in groups)
        api_url = ''.join([api_url, '&group=', groups])

    response = _get_from_cache(api_url)
    posts = _normalise_posts(json.loads(response.text))

    return posts[0] if posts else None


def _embed_post_data(post):
    if '_embedded' not in post:
        return post
    embedded = post['_embedded']
    post['author'] = _normalise_user(embedded['author'][0])
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


@app.route('/')
@app.route('/<category>/')
def index(category=[]):
    groups = []
    if category:
        if category == 'press-centre':
            category = 'canonical-announcements'

        groups = _get_groups_by_slug(slugs=category)

        if not groups:
            return flask.render_template(
                '404.html'
            )

    groups_id = [str(group['id']) for group in groups]

    page = flask.request.args.get('page')
    posts, metadata = _get_posts(
        groups=groups_id,
        page=page
    )

    featured_post = _get_featured_post(groups_id)

    if category:
        return flask.render_template(
            'group.html',
            posts=posts,
            category=groups[0] if groups else None,
            featured_post=featured_post,
            **metadata
        )
    else:
        return flask.render_template(
            'index.html',
            posts=posts,
            featured_post=featured_post,
            **metadata
        )


@app.route('/tag/<slug>/')
def tag_index(slug):
    api_url = ''.join([INSIGHTS_URL, '/tags?slug=', slug])
    response = _get_from_cache(api_url)

    response_text = json.loads(response.text)
    if response_text:
        tag = response_text[0]
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
    api_url = ''.join([INSIGHTS_URL, '/posts?_embed&slug=', slug])
    response = _get_from_cache(api_url)
    data = json.loads(response.text)[0]
    data = _normalise_post(data)
    data['related_posts'] = _get_related_posts(data)
    return flask.render_template('post.html', post=data)


@app.route('/author/<slug>/')
def user(slug):
    api_url = ''.join([INSIGHTS_URL, '/users?_embed&slug=', slug])
    response = _get_from_cache(api_url)
    data = json.loads(response.text)[0]
    data = _normalise_user(data)
    return flask.render_template('author.html', author=data)
