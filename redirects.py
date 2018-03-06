# Core
import os
import re

# External
import flask
import yaml
import yamlordereddictloader


class YamlRegexMap:
    def __init__(self, filepath):
        """
        Given the path to a YAML file of RegEx mappings like:

            hello/(?P<person>.*)?: "/say-hello?name={person}"
            google/(?P<search>.*)?: "https://google.com/?q={search}"

        Return a list of compiled Regex matches and destination strings:

            [
                (<regex>, "/say-hello?name={person}"),
                (<regex>, "https://google.com/?q={search}"),
            ]
        """

        self.matches = []

        if os.path.isfile(filepath):
            with open(filepath) as redirects_file:
                lines = yaml.load(
                    redirects_file,
                    Loader=yamlordereddictloader.Loader
                )

                if lines:
                    for url_match, target_url in lines.items():
                        if url_match[0] != '/':
                            url_match = '/' + url_match

                        self.matches.append(
                            (re.compile(url_match), target_url)
                        )

    def get_target(self, url_path):
        for (match, target) in self.matches:
            result = match.fullmatch(url_path)

            if result:
                parts = {}
                for name, value in result.groupdict().items():
                    parts[name] = value or ''

                target_url = target.format(**parts)

                if flask.request.query_string:
                    target_url += (
                        '?' + flask.request.query_string.decode('utf-8')
                    )

                return target_url


def prepare_redirects(
    permanent_redirects_path='permanent-redirects.yaml',
    redirects_path='redirects.yaml'
):
    """
    Create a regex map from the provided yaml files,
    and return a view function "apply_redirects" which encloses
    the maps to apply redirect where relevant.

    Usage:

        import flask
        from redirects import prepare_redirects
        app = flask.Flask(__name__)
        apply_redirects = prepare_redirects(
            permanent_redirects_path='permanent-redirects.yaml',
            redirects_path='redirects.yaml'
        )
        app.before_request(apply_redirects)
    """

    permanent_redirect_map = YamlRegexMap(permanent_redirects_path)
    redirect_map = YamlRegexMap(redirects_path)

    def apply_redirects():
        """
        Process the two mappings defined above
        of permanent and temporary redirects to target URLs,
        to send the appropriate redirect responses
        """

        permanent_redirect_url = permanent_redirect_map.get_target(
            flask.request.path
        )
        if permanent_redirect_url:
            return flask.redirect(permanent_redirect_url, code=301)

        redirect_url = redirect_map.get_target(flask.request.path)
        if redirect_url:
            return flask.redirect(redirect_url)

    return apply_redirects
