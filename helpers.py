# Core
import time
import datetime
import warnings
from urllib.parse import urlencode

# External
import feedparser
import logging
import calendar
import requests_cache


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

    # Set cache expire time
    cached_session = requests_cache.CachedSession(
        name="hour-cache",
        expire_after=datetime.timedelta(hours=1),
        old_data_on_error=True
    )

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
