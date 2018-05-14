# Third party
import requests

# Local
import helpers
import feeds


API_URL = 'https://admin.blog.ubuntu.com/wp-json/wp/v2'


def _embed_resource_data(resource):
    if '_embedded' not in resource:
        return resource
    embedded = resource['_embedded']
    if 'wp:featuredmedia' not in embedded:
        return resource
    resource['featuredmedia'] = embedded['wp:featuredmedia'][0]
    return resource


def _normalise_resources(posts):
    for post in posts:
        post = _embed_resource_data(post)
    return posts


def get(endpoint, parameters={}):
    """
    Query the blog API (admin.blog.ubuntu.com) using the cache
    """

    return feeds.cached_request(
        helpers.build_url(API_URL, endpoint, parameters)
    )


def get_topics(post_id):
    """
    Get the topics for a post
    """

    response = get('topic', {'post': post_id})

    return response.json()


def get_tags(slugs=[], post_id=''):
    """
    Get tag data from API,
    optionally filtering by slug or post_id
    """

    response = get(
        endpoint='tags',
        parameters={
            "slug": ','.join(slugs),
            "post": post_id
        }
    )

    return response.json()


def get_posts(
    page=1, per_page=12, query='', sticky=None,
    slugs=[], group_ids=[], category_ids=[], tag_ids=[], author_ids=[],
    before=None, after=None
):
    """
    Get posts by querying the Wordpress API,
    including retrieving pagination information.

    Gracefully handle errors for pages that don't exist,
    returning empty data instead of an error.

    Allow filtering on various criteria, using sensible defaults.
    """

    try:
        response = get(
            'posts',
            {
                '_embed': True,
                'per_page': per_page,
                'page': page,
                'search': query,
                'sticky': sticky,
                'slug': ','.join(slugs),
                'group': helpers.join_ids(group_ids),
                'categories': helpers.join_ids(category_ids),
                'tags': helpers.join_ids(tag_ids),
                'author': helpers.join_ids(author_ids),
                'before': before.isoformat() if before else None,
                'after': after.isoformat() if after else None
            }
        )
    except requests.exceptions.HTTPError as request_error:
        response = request_error.response.json()

        if (
            type(response) is dict and
            response.get('code') == 'rest_post_invalid_page_number'
        ):
            # The page doesn't exist, so set everything to empty
            posts = []
            total_posts = None
            total_pages = None
        else:
            # We don't recognise this error, re-raise it
            raise request_error
    else:
        posts = response.json()
        total_pages = helpers.to_int(
            response.headers.get('X-WP-TotalPages'),
            None
        )
        total_posts = helpers.to_int(
            response.headers.get('X-WP-Total'),
            None
        )

    posts = _normalise_resources(posts)

    return posts, total_posts, total_pages


def get_category(category_id):
    return get('categories/' + str(category_id)).json()


def get_categories(slugs=[]):
    response = get('categories', {'slug': ','.join(slugs)})

    return response.json()


def get_users(slugs=[]):
    response = get('users', {'slug': ','.join(slugs)})

    return response.json()


def get_group(group_id):
    return get('group/' + str(group_id)).json()


def get_groups(slugs=[]):
    return get('group', {'slug': ','.join(slugs)}).json()
