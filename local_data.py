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
