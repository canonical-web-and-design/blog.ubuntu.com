# Core
import time
import datetime
from urllib.parse import urlparse

# Third-party
import feedparser
import logging
import requests_cache
import prometheus_client
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException


# Prometheus metric exporters
requested_from_cache_counter = prometheus_client.Counter(
    "feed_requested_from_cache",
    "A counter of requests retrieved from the cache",
    ["domain"],
)
failed_requests = prometheus_client.Counter(
    "feed_failed_requests",
    "A counter of requests retrieved from the cache",
    ["error_name", "domain"],
)
request_latency_seconds = prometheus_client.Histogram(
    "feed_request_latency_seconds",
    "Feed requests retrieved",
    ["domain", "code"],
    buckets=[0.25, 0.5, 0.75, 1, 2],
)

# Cache session settings
cached_session = requests_cache.CachedSession(
    name="hour-cache",
    expire_after=datetime.timedelta(hours=1),
    backend="memory",
    old_data_on_error=True,
)
cached_session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
        )
    ),
)


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
            "Attempt to get feed failed: {}".format(str(request_error))
        )
        return False

    try:
        feed_data = feedparser.parse(response.text)
        if not feed_data.feed:
            logger.warning("No valid feed data found at {}".format(url))
            return False
        content = feed_data.entries
    except Exception as parse_error:
        logger.warning(
            "Failed to parse feed from {}: {}".format(url, str(parse_error))
        )
        return False

    if exclude_items_in:
        exclude_ids = [item["guid"] for item in exclude_items_in]
        content = [item for item in content if item["guid"] not in exclude_ids]

    content = content[offset:end]

    for item in content:
        updated_time = time.mktime(item["updated_parsed"])
        item["updated_datetime"] = datetime.datetime.fromtimestamp(
            updated_time
        )

    return content


def cached_request(url):
    """
    Retrieve the response from the requests cache.
    If the cache has expired then it will attempt to update the cache.
    If it gets an error, it will use the cached response, if it exists.
    """

    response = cached_session.get(url, timeout=3)

    try:
        response.raise_for_status()
    except RequestException as request_error:
        failed_requests.labels(
            error_name=type(request_error).__name__,
            domain=urlparse(url).netloc,
        ).inc()
        raise request_error

    if hasattr(response, "from_cache") and response.from_cache:
        requested_from_cache_counter.labels(domain=urlparse(url).netloc).inc()
    else:
        request_latency_seconds.labels(
            domain=urlparse(url).netloc, code=response.status_code
        ).observe(response.elapsed.total_seconds())

    return response
