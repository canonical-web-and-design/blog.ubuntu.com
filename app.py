# Core
import urllib

# Third-party
import flask
from flask import request

# Local
import api
from helpers import get_rss_feed_content, monthname
from werkzeug.routing import BaseConverter
from datetime import datetime

INSIGHTS_URL = 'https://insights.ubuntu.com'

app = flask.Flask(__name__)
app.jinja_env.filters['monthname'] = monthname

class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app.url_map.converters['regex'] = RegexConverter


@app.route('/')
def homepage():
    search = request.args.get('search')

    if search:
        result = {}

        posts = api.search_posts(search)

        result["posts"] = posts
        result["count"] = len(posts)
        result["query"] = search
        return flask.render_template('search.html', result=result)

    page = flask.request.args.get('page')
    posts, metadata = api.get_posts(page=page, per_page=13)

    webinars = get_rss_feed_content(
        'https://www.brighttalk.com/channel/6793/feed'
    )

    featured_post = api.get_featured_post()
    homepage_posts = []

    for post in posts:
        if post['id'] != featured_post['id']:
            homepage_posts.append(post)

    return flask.render_template(
        'index.html',
        posts=homepage_posts[:12],
        featured_post=featured_post,
        webinars=webinars,
        **metadata
    )


@app.route('/<group>/')
@app.route('/<group>/<category>/')
def group_category(group=[], category='all'):
    groups = []
    categories = []

    if group:
        if group == 'press-centre':
            group = 'canonical-announcements'

        groups = api.get_group_by_slug(group)

        if not groups:
            return flask.render_template(
                '404.html'
            )
        group_details = api.get_group_details(group)  # read the json file

    groups_id = int(groups['id']) if groups else None

    categories = api.get_category_by_slug(category)
    categories_id = [categories['id']] if categories['id'] else []

    page = flask.request.args.get('page')
    posts, metadata = api.get_posts(
        groups_id=groups_id,
        categories=categories_id,
        page=page,
        per_page=12
    )

    if group == 'canonical-announcements':
        return flask.render_template(
            'press-centre.html',
            posts=posts,
            group=groups if groups else None,
            group_details=group_details,
            category=category if category else None,
            **metadata
        )
    elif group:
        return flask.render_template(
            'group.html',
            posts=posts,
            group=groups if groups else None,
            group_details=group_details,
            category=category if category else None,
            **metadata
        )
    else:
        return flask.render_template(
            'index.html',
            posts=posts,
            featured_post=featured_post,
            webinars=webinars,
            **metadata
        )

@app.route('/topics/<slug>/')
def topic_name(slug):
    topic = api.get_topic_details(slug)

    if not topic:
        flask.abort(404)

    tags = api.get_tag(slug=topic['slug'])

    if not tags:
        flask.abort(404)

    if tags:
        tag = tags[0]
        page = flask.request.args.get('page')
        posts, metadata = api.get_posts(tags=[tag['id']], page=page)

    return flask.render_template(
        'topics.html', topic=topic, posts=posts, **metadata
    )


@app.route('/tag/<slug>/')
def tag_index(slug):
    response_json = api.get_tag(slug)

    if response_json:
        tag = response_json[0]
        page = flask.request.args.get('page')
        posts, metadata = api.get_posts(tags=[tag['id']], page=page)

        return flask.render_template(
            'tag.html', posts=posts, tag=tag, **metadata
        )
    else:
        return flask.render_template(
            '404.html'
        )

@app.route('/archives/<regex("[0-9]{4}"):year>/')
def archives_year(year):
    result = api.get_archives(year)
    return flask.render_template('archives.html', result=result, today=datetime.utcnow())

@app.route('/archives/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>/')
def archives_year_month(year, month):
    result = api.get_archives(year, month)
    return flask.render_template('archives.html', result=result, today=datetime.utcnow())

@app.route('/archives/<group>/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>/')
def archives_group_year_month(group, year, month):
    group_id = ''
    groups = []
    if group:
        if group == 'press-centre':
            group = 'canonical-announcements'

        groups = api.get_group_by_slug(group)
        group_id = int(groups['id']) if groups else None
        group_name = groups['name'] if groups else None

        if not group_id:
            return flask.render_template(
                '404.html'
            )
    result = api.get_archives(year, month, group_id, group_name)
    return flask.render_template('archives.html', result=result, today=datetime.utcnow())

@app.route('/archives/<group>/<regex("[0-9]{4}"):year>/')
def archives_group_year(group, year):
    group_id = ''
    groups = []
    if group:
        if group == 'press-centre':
            group = 'canonical-announcements'

        groups = api.get_group_by_slug(group)
        group_id = int(groups['id']) if groups else None
        group_name = groups['name'] if groups else None

        if not group_id:
            return flask.render_template(
                '404.html'
            )
    result = api.get_archives(year, None, group_id, group_name)
    return flask.render_template('archives.html', result=result)

@app.route('/archives/<group>/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>/')
def archives_group_year_month(group, year, month):
    if group == 'press-centre':
        group = 'canonical-announcements'

    groups = api.get_group_by_slug(group)
    if not groups:
        flask.abort(404)

    group_id = int(groups['id']) if groups else None
    group_name = groups['name'] if groups else None

    result = api.get_archives(year, month, group_id, group_name)
    return flask.render_template('archives.html', result=result)

@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<regex("[0-9]{2}"):day>'
    '/<slug>/'
)
def post(year, month, day, slug):
    return flask.render_template('post.html', post=api.get_post(slug))


@app.route('/author/<slug>/')
def user(slug):
    return flask.render_template('author.html', author=api.get_author(slug))


@app.route('/admin/')
@app.route('/feed/')
@app.route('/wp-content/')
@app.route('/wp-includes/')
@app.route('/wp-login.php/')
def redirect_wordpress_login():
    path = flask.request.path
    if (flask.request.args):
        path = '?'.join([path, urllib.parse.urlencode(flask.request.args)])

    return flask.redirect(INSIGHTS_URL + path)


@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404


@app.errorhandler(410)
def page_deleted(e):
    return flask.render_template('410.html'), 410


@app.errorhandler(500)
def server_error(e):
    return flask.render_template('500.html'), 500
