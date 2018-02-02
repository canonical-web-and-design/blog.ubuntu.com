"""
The code in this file is TO BE DEPRECATED.
The methods retrieve data stored locally within the repository
that should instead be retrieved from the API.

Each of the methods in this file should be gradually
replaced by API-based methods.

@todo: Remove this file
"""

# Core
import json


GROUPBYID = {
    1706: {'slug': 'cloud-and-server', 'name': 'Cloud and server'},
    1666: {'slug': 'internet-of-things', 'name': 'Internet of things'},
    1479: {'slug': 'desktop', 'name': 'Desktop'},
    2100: {
        'slug': 'canonical-announcements', 'name': 'Canonical announcements'
    },
    1707: {'slug': 'phone-and-tablet', 'name': 'Phone and tablet'},
    2051: {'slug': 'people-and-culture', 'name': 'People and culture'},
}
GROUPBYSLUG = {
    'cloud-and-server': {'id': 1706, 'name': 'Cloud and server'},
    'internet-of-things': {'id': 1666, 'name': 'Internet of things'},
    'desktop': {'id': 1479, 'name': 'Desktop'},
    'canonical-announcements': {'id': 2100, 'name': 'Canonical announcements'},
    'phone-and-tablet': {'id': 1707, 'name': 'Phone and tablet'},
    'people-and-culture': {'id': 2051, 'name': 'People and culture'},
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
    2099: {
        "name": "Canonical announcements", "slug": "canonical-announcements"
    },
    1921: {"name": "Desktop", "slug": "desktop"},
    1924: {"name": "Internet of Things", "slug": "internet-of-things"},
    2052: {"name": "People and culture", "slug": "people-and-culture"},
    1340: {"name": "Phone", "slug": "phone"},
    1922: {"name": "Server", "slug": "server"},
    1481: {"name": "Tablet", "slug": "tablet"},
    1482: {"name": "TV", "slug": "tv"},
}


def get_category_by_id(category_id):
    global CATEGORIESBYID
    return CATEGORIESBYID[category_id]


def get_category_by_slug(category_name):
    global CATEGORIESBYSLUG
    return CATEGORIESBYSLUG[category_name]


def get_group_by_id(group_id):
    global GROUPBYID
    return GROUPBYID[group_id]


def get_group_by_slug(group_slug):
    global GROUPBYSLUG
    return GROUPBYSLUG[group_slug]


def get_topic_by_id(topic_id):
    global TOPICBYID
    return TOPICBYID[topic_id]


def get_group_details(slug):
    with open('data/groups.json') as file:
        groups = json.load(file)

    for group in groups:
        if group['slug'] == slug:
            return group


def get_topic_details(slug):
    with open('data/topics.json') as file:
        topics = json.load(file)

    for topic in topics:
        if topic['slug'] == slug:
            return topic
