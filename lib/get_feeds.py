import feedparser
import logging
import json
from datetime import datetime
from requests_cache import CachedSession
from time import mktime


logger = logging.getLogger(__name__)
requests_timeout = 10
expiry_seconds = 300

cached_request = CachedSession(
    expire_after=expiry_seconds,
)


def get_json_feed_content(url, offset=0, limit=None):
    """
    Get the entries in a JSON feed
    """

    end = limit + offset if limit is not None else None

    try:
        response = cached_request.get(url, timeout=requests_timeout)
        response.raise_for_status()
    except Exception as request_error:
        logger.warning(
            'Attempt to get feed failed: {}'.format(str(request_error))
        )
        return False

    try:
        content = json.loads(response.text)
    except Exception as parse_error:
        logger.warning(
            'Failed to parse feed from {}: {}'.format(url, str(parse_error))
        )
        return False

    return content[offset:end]


def get_rss_feed_content(url, offset=0, limit=None, exclude_items_in=None):
    """
    Get the entries from an RSS feed
    """

    end = limit + offset if limit is not None else None

    try:
        response = cached_request.get(url, timeout=requests_timeout)
        response.raise_for_status()
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
        updated_time = mktime(item['updated_parsed'])
        item['updated_datetime'] = datetime.fromtimestamp(updated_time)

    return content
