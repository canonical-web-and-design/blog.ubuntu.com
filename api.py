# Core
import datetime
import calendar
import re
import json
import textwrap
from urllib.parse import urlsplit

# Third party
import dateutil.parser
import requests_cache

# Local
from helpers import join_ids, build_url
import local_data


API_URL = 'https://admin.insights.ubuntu.com/wp-json/wp/v2'


# Set cache expire time
cached_session = requests_cache.CachedSession(
    name="hour-cache",
    expire_after=datetime.timedelta(hours=1),
    old_data_on_error=True
)

# Requests should timeout after 2 seconds in total
request_timeout = 10


def get(endpoint, parameters={}):
    """
    Retrieve the response from the requests cache.
    If the cache has expired then it will attempt to update the cache.
    If it gets an error, it will use the cached response, if it exists.
    """

    url = build_url(API_URL, endpoint, parameters)

    response = cached_session.get(url)

    response.raise_for_status()

    return response


def _embed_post_data(post):
    if '_embedded' not in post:
        return post
    embedded = post['_embedded']
    post['author'] = _normalise_user(embedded['author'][0])
    post['category'] = local_data.get_category_by_id(
        post['categories'][0]
    )
    if post['topic']:
        post['topics'] = local_data.get_topic_by_id(
            post['topic'][0]
        )
    if 'groups' not in post and post['group']:
        post['groups'] = local_data.get_group_by_id(
            int(post['group'][0])
        )
    return post


def _normalise_user(user):
    link = user['link']
    path = urlsplit(link).path
    user['relative_link'] = path.rstrip('/')
    return user


def _normalise_posts(posts, groups_id=None):
    for post in posts:
        if post['excerpt']['rendered']:
            # replace headings (e.g. h1) to paragraphs
            post['excerpt']['rendered'] = re.sub(
                r"h\d>", "p>",
                post['excerpt']['rendered']
            )

            # remove images
            post['excerpt']['rendered'] = re.sub(
                r"<img(.[^>]*)?", "",
                post['excerpt']['rendered']
            )

            # shorten to 250 chars, on a wordbreak and with a ...
            post['excerpt']['rendered'] = textwrap.shorten(
                post['excerpt']['rendered'],
                width=250,
                placeholder="&hellip;"
            )

            # if there is a [...] replace with ...
            post['excerpt']['rendered'] = re.sub(
                r"\[\&hellip;\]", "&hellip;",
                post['excerpt']['rendered']
            )
        post = _normalise_post(post, groups_id=groups_id)
    return posts


def _normalise_post(post, groups_id=None):
    link = post['link']
    path = urlsplit(link).path
    post['relative_link'] = path.rstrip('/')
    post['formatted_date'] = datetime.datetime.strftime(
        dateutil.parser.parse(post['date']),
        "%d %B %Y"
    ).lstrip("0").replace(" 0", " ")

    if groups_id:
        post['groups'] = local_data.get_group_by_id(groups_id)

    post = _embed_post_data(post)
    return post


def search_posts(search):
    response = get('posts', {'_embed': True, 'search': search})
    posts = _normalise_posts(json.loads(response.text))

    return posts


def get_tag(slug):
    response = get('tags', {'slug': slug})

    return json.loads(response.text)


def get_post(slug):
    response = get('posts', {'_embed': True, 'slug': slug})
    post = json.loads(response.text)[0]
    post['tags'] = get_tag_details_from_post(post['id'])
    post = _normalise_post(post)
    post['related_posts'] = get_related_posts(post)

    return post


def get_author(slug):
    response = get('users', {'_embed': True, 'slug': slug})
    user = json.loads(response.text)[0]
    user = _normalise_user(user)
    user['recent_posts'] = get_user_recent_posts(user['id'])

    return user


def get_posts(
    groups_id=None, categories=[], tags=[], page=1, per_page=12,
    before=None, after=None
):
    response = get(
        'posts',
        {
            '_embed': True,
            'per_page': per_page,
            'page': page,
            'group': groups_id,
            'categories': join_ids(categories),
            'tags': join_ids(tags),
            'before': before,
            'after': after
        }
    )

    headers = response.headers
    page = int(page or 1)
    total_pages = int(headers.get('X-WP-TotalPages'))

    pagination_start = page - 2
    if pagination_start <= 1:
        pagination_start = 1

    if total_pages - pagination_start < 5 and pagination_start > 3:
        pagination_start = total_pages - 4

    metadata = {
        'current_page': page,
        'total_pages': total_pages,
        'total_posts': int(headers.get('X-WP-Total')),
        'pagination_start': pagination_start,
    }

    posts = _normalise_posts(
        json.loads(response.text),
        groups_id=groups_id
    )

    return posts, metadata


def get_archives(
    year,
    month=None, group_id=None, group_name='Archives',
    categories=[], tags=[], page=1, per_page=100
):
    result = {}
    startmonth = 1
    endmonth = 12
    if month:
        startmonth = month
        endmonth = month
    last_day = calendar.monthrange(int(year), int(endmonth))[1]
    after = datetime.datetime(int(year), int(startmonth), 1)
    before = datetime.datetime(int(year), int(endmonth), last_day)

    posts, metadata = get_posts(
        before=before.isoformat(),
        after=after.isoformat(),
        page=page
    )

    if month:
        result["date"] = after.strftime("%B") + ' ' + str(year)
    else:
        result["date"] = str(year)
    if group_name != "Archives":
        group_name = group_name + ' archives'

    result["title"] = group_name
    result["posts"] = posts
    result["count"] = len(posts)
    return result, metadata


def get_related_posts(post):
    response = get(
        'tags',
        {
            'embed': True,
            'per_page': 3,
            'post': post['id']
        }
    )
    tags = json.loads(response.text)

    tag_ids = [tag['id'] for tag in tags]
    posts, meta = get_posts(tags=tag_ids)
    posts = _normalise_posts(posts)

    return posts


def get_user_recent_posts(user_id, limit=5):
    response = get(
        'posts',
        {
            'embed': True,
            'author': user_id,
            'per_page': limit,
        }
    )
    posts = _normalise_posts(json.loads(response.text))

    return posts


def get_tag_details_from_post(post_id):
    response = get('tags', {'post': post_id})
    tags = json.loads(response.text)

    return tags


def get_featured_post(groups_id=None, categories=[], per_page=1):
    response = get(
        'posts',
        {
            '_embed': True,
            'sticky': True,
            'per_page': per_page,
            'group': groups_id,
            'categories': join_ids(categories)
        }
    )
    posts = _normalise_posts(json.loads(response.text), groups_id=groups_id)

    return posts[0] if posts else None
