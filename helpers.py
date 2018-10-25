# Core
import re
import textwrap
import warnings
from urllib.parse import urlencode, urlsplit
import datetime

# External
import dateutil.parser
import calendar
import werkzeug

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

    if kwargs.get("group_ids"):
        force_group = kwargs.get("group_ids")[0]

    for post in posts:
        post = format_post(post)

        post["group"] = get_first_group(
            post.get("group", ""), force_group=force_group
        )

        post["category"] = get_first_category(post["categories"])

    return posts, total_posts, total_pages


def get_first_group(group_ids, force_group=None):
    """
    Retrieve the first group from a list of group_ids
    """

    if force_group:
        group_id = force_group
    else:
        group_id = group_ids[0] if group_ids else None

    return api.get_group(group_id) if group_id else None


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

    if "author" in post["_embedded"] and post["_embedded"]["author"]:
        post["author"] = post["_embedded"]["author"][0]
        post["author"]["link"] = urlsplit(post["author"]["link"]).path.rstrip(
            "/"
        )
    post["link"] = urlsplit(post["link"]).path.rstrip("/")
    post["summary"] = format_summary(post["excerpt"]["rendered"])
    post["date"] = format_date(post["date"])

    if post["_start_month"]:
        start_month_name = get_month_name(int(post["_start_month"]))
        post["start_date"] = "{} {} {}".format(
            post["_start_day"], start_month_name, post["_start_year"]
        )

    if post["_end_month"]:
        end_month_name = get_month_name(int(post["_end_month"]))
        post["end_date"] = "{} {} {}".format(
            post["_end_day"], end_month_name, post["_end_year"]
        )

    if post["content"]:
        CLOUDINARY = (
            "https://res.cloudinary.com/"
            "canonical/image/fetch/q_auto,f_auto,"
        )
        post["content"]["rendered"] = re.sub(
            r"img(.*)src=\"(.[^\"]*)\"",
            r'img\1 src="{url}w_560/\2"'
            r'srcset="{url}w_375/\2 375w,'
            r'{url}w_480/\2 480w, {url}w_560/\2 560w"'
            r'sizes="(max-width: 375px) 280px,'
            r"(max-width: 480px) 440px,"
            r'560px"'.format(url=CLOUDINARY),
            post["content"]["rendered"],
        )

    return post


def get_month_name(month_index):
    """
    Get the month name from it's number, e.g.:
    January
    """

    return datetime.date(1900, month_index, 1).strftime("%B")


def format_date(date):
    """
    Make the date just how we like it, e.g.:
    1 January 2017
    """

    return dateutil.parser.parse(date).strftime("%-d %B %Y")


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

    return ",".join([str(item) for item in ids])


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

    return base_url.rstrip("/") + "/" + endpoint.lstrip("/") + query_string


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


def filter_tags_for_display(tags):
    """
    Filter out specific tags to remove noise

    :param tags: list of wordpress tags
    :return: list of wordpress tags
    """
    # snapcraft tags
    def is_snapcraft(tag):
        return tag["name"].startswith("sc:")

    return [tag for tag in tags if not is_snapcraft(tag)]


class RegexConverter(werkzeug.routing.BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]
