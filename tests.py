#! /usr/bin/env python3

# Core
import unittest
import time

# Local
import app
from api import get


def _get_posts():
    response = get(
        'posts',
        {
            '_embed': True,
            'per_page': 3,
            'group': "1479,1666"
        }
    )

    return response.json()


class WebAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True

    def test_api_cache(self):
        # Warm cache
        initial_posts = _get_posts()

        # Make a request with the cache warmed
        start = time.time()
        subsequent_posts = _get_posts()
        request_time = time.time() - start

        assert type(initial_posts) == list
        assert initial_posts == subsequent_posts
        assert request_time < 1


if __name__ == '__main__':
    unittest.main()
