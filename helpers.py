# Core
import time
import datetime
import re
import textwrap
import warnings
from urllib.parse import urlencode, urlsplit

# External
import dateutil.parser
import feedparser
import logging
import calendar
import requests_cache
import werkzeug
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Local
import api


def get_formatted_posts(**kwargs):
    """
    Get posts from API, then format the summary, date and link
    """

    posts, total_posts, total_pages = api.get_posts(**kwargs)

    for post in posts:
        post = format_post(post)

    return posts, total_posts, total_pages


def get_formatted_expanded_posts(**kwargs):
    """
    Get posts from API, then format them and add the data for the first group
    and category
    """

    posts, total_posts, total_pages = api.get_posts(**kwargs)

    force_group = None

    if kwargs.get('group_ids'):
        force_group = kwargs.get('group_ids')[0]

    for post in posts:
        post = format_post(post)
        post['group'] = get_first_group(post['group'], force_group=force_group)
        post['category'] = get_first_category(post['categories'])

    return posts, total_posts, total_pages


def get_first_group(group_ids, force_group=None):
    """
    Retrieve the first group from a list of group_ids
    """

    if force_group:
        group_id = force_group
    else:
        group_id = group_ids[0] if group_ids else None

    return api.get_group(group_id)


def get_first_category(category_ids):
    """
    Retrieve the first group from a list of group_ids
    """

    return api.get_category(category_ids[0]) if category_ids else None


def format_post(post):
    """
    Transform post data by:
    - Formatting the excerpt
    - Putting the author at post['author']
    - Formatting the data as e.g. 1 January 2017
    - Making the link relative
    """

    if 'author' in post['_embedded'] and post['_embedded']['author']:
        post['author'] = post['_embedded']['author'][0]
        post['author']['link'] = urlsplit(
            post['author']['link']
        ).path.rstrip('/')
    post['link'] = urlsplit(post['link']).path.rstrip('/')
    post['summary'] = format_summary(post['excerpt']['rendered'])
    post['date'] = format_date(post['date'])

    return post


def format_date(date):
    """
    Make the date just how we like it, e.g.:
    1 January 2017
    """

    return dateutil.parser.parse(date).strftime('%-d %B %Y')


def format_summary(excerpt):
    """
    Format the excerpt in a post:
    - Shorten to 250 chars
    - Remove images
    - Make headings into paragraphs
    """

    # shorten to 250 chars, on a wordbreak and with a ...
    summary = textwrap.shorten(excerpt, width=250, placeholder="&hellip;")

    # replace headings (e.g. h1) to paragraphs
    summary = re.sub(r"h\d>", "p>", summary)

    # remove images
    summary = re.sub(r"<img(.[^>]*)?", "", summary)

    # if there is a [...] replace with ...
    summary = re.sub(r"\[\&hellip;\]", "&hellip;", summary)

    return summary


def monthname(month_number):
    return calendar.month_abbr[month_number]


def join_ids(ids):
    """
    Given a list of ids, turn it into a string, separated by commas
    - including casting all types to a string
    """

    return ','.join([str(item) for item in ids])


def build_url(base_url, endpoint, parameters):
    """
    Build a URL up from a base_url, an endpoint and some query parameters
    """

    query_string = ""

    # Remove empty arguments
    for key, value in list(parameters.items()):
        if type(value) == bool:
            value = str(value)

        if not value:
            del parameters[key]

    if parameters:
        query_string = "?" + urlencode(parameters)

    return base_url.rstrip('/') + '/' + endpoint.lstrip('/') + query_string


def get_rss_feed_content(url, offset=0, limit=6, exclude_items_in=None):
    """
    Get the entries from an RSS feed

    Inspired by https://github.com/canonical-webteam/get-feeds/,
    minus Django-specific stuff.
    """

    logger = logging.getLogger(__name__)
    end = limit + offset if limit is not None else None

    try:
        response = cached_request(url)
    except Exception as request_error:
        logger.warning(
            'Attempt to get feed failed: {}'.format(str(request_error))
        )
        return False

    try:
        feed_data = feedparser.parse(response.text)
        if not feed_data.feed:
            logger.warning('No valid feed data found at {}'.format(url))
            return False
        content = feed_data.entries
    except Exception as parse_error:
        logger.warning(
            'Failed to parse feed from {}: {}'.format(url, str(parse_error))
        )
        return False

    if exclude_items_in:
        exclude_ids = [item['guid'] for item in exclude_items_in]
        content = [item for item in content if item['guid'] not in exclude_ids]

    content = content[offset:end]

    for item in content:
        updated_time = time.mktime(item['updated_parsed'])
        item['updated_datetime'] = datetime.datetime.fromtimestamp(
            updated_time
        )

    return content


def cached_request(url):
    """
    Retrieve the response from the requests cache.
    If the cache has expired then it will attempt to update the cache.
    If it gets an error, it will use the cached response, if it exists.
    """

    retries = Retry(
        total=5,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504]
    )

    # Set cache expire time
    cached_session = requests_cache.CachedSession(
        name="hour-cache",
        expire_after=datetime.timedelta(hours=1),
        old_data_on_error=True
    )
    cached_session.mount('https://', HTTPAdapter(max_retries=retries))

    response = cached_session.get(url, timeout=2)

    response.raise_for_status()

    return response


def ignore_warnings(warning_to_ignore):
    """
    Decorator to ignore ResourceWarnings in a function,
    as they are often erroneous. See:
    https://github.com/boto/boto3/issues/454#issuecomment-324782994
    """

    def ignore_warnings_inner(test_func):
        def wrapper(*args, **kwargs):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", warning_to_ignore)
                return test_func(*args, **kwargs)

        return wrapper

    return ignore_warnings_inner


def to_int(value_to_convert, default=None):
    """
    Attempt to convert something to an int.
    If it fails, use the default
    """

    try:
        return int(value_to_convert)
    except (ValueError, TypeError):
        return default


class RegexConverter(werkzeug.routing.BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]
