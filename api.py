# Core
import datetime
import calendar
import re
import json
import textwrap
from urllib.parse import urlsplit

# Third party
import dateutil.parser
import requests

# Local
from helpers import build_url, cached_request, join_ids
import local_data


API_URL = 'https://admin.insights.ubuntu.com/wp-json/wp/v2'


def get(endpoint, parameters={}):
    """
    Query the Insights API (admin.insights.ubuntu.com) using the cache
    """

    return cached_request(build_url(API_URL, endpoint, parameters))


def get_paginated(endpoint, parameters={}):
    """
    Query the insights API, parsing pagination information,
    and gracefully handling errors when the page doesn't exist
    """

    try:
        response = get(endpoint, parameters)
    except requests.exceptions.HTTPError as request_error:
        response = request_error.response.json()

        if response.get('code') == 'rest_post_invalid_page_number':
            # The page doesn't exist, so set everything to empty
            items = []
            total_posts = None
            total_pages = None
            pagination_start = None
        else:
            # We don't recognise this error, re-raise it
            raise request_error
    else:
        items = response.json()
        total_pages = int(response.headers.get('X-WP-TotalPages'))
        total_posts = int(response.headers.get('X-WP-Total'))

        pagination_start = parameters['page'] - 2
        if pagination_start <= 1:
            pagination_start = 1

        if total_pages - pagination_start < 5 and pagination_start > 3:
            pagination_start = total_pages - 4

    return items, {
        'current_page': parameters['page'],
        'total_pages': total_pages,
        'total_posts': total_posts,
        'pagination_start': pagination_start,
    }


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
    response = get(
        'posts',
        {'_embed': True, 'search': search}
    )
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
    user = _normalise_user(json.loads(response.text)[0])
    user['recent_posts'] = get_user_recent_posts(user['id'])

    return user


def get_posts(
    groups_id=None, categories=[], tags=[], page=1, per_page=12,
    before=None, after=None
):
    items, page_information = get_paginated(
        'posts',
        parameters={
            '_embed': True,
            'page': page,
            'per_page': per_page,
            'group': groups_id,
            'categories': join_ids(categories),
            'tags': join_ids(tags),
            'before': before,
            'after': after
        }
    )

    posts = _normalise_posts(items, groups_id=groups_id)

    return posts, page_information


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
