# Core
from urllib.parse import urlparse, urlunparse, unquote

# Third-party
import flask
from datetime import datetime
from werkzeug.routing import BaseConverter

# Local
import api
import local_data
import helpers
import redirects


INSIGHTS_URL = 'https://insights.ubuntu.com'

app = flask.Flask(__name__)
app.jinja_env.filters['monthname'] = helpers.monthname
app.url_map.strict_slashes = False


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


apply_redirects = redirects.prepare_redirects(
    permanent_redirects_path='permanent-redirects.yaml',
    redirects_path='redirects.yaml'
)
app.before_request(apply_redirects)

app.url_map.converters['regex'] = RegexConverter


@app.before_request
def clear_trailing():
    """
    Remove trailing slashes from all routes
    We like our URLs without slashes
    """

    parsed_url = urlparse(unquote(flask.request.url))
    path = parsed_url.path

    if path != '/' and path.endswith('/'):
        new_uri = urlunparse(
            parsed_url._replace(path=path[:-1])
        )

        return flask.redirect(new_uri)


@app.route('/')
def homepage():
    page = flask.request.args.get('page')
    posts, metadata = api.get_posts(page=page, per_page=13)

    webinars = helpers.get_rss_feed_content(
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


@app.route('/search/')
def search():
    query = flask.request.args.get('q') or ''

    posts = api.search_posts(query) if query else []

    return flask.render_template(
        'search.html',
        result={
            "posts": posts,
            "count": len(posts),
            "query": query
        }
    )


@app.route('/<group_slug>')
@app.route('/<group_slug>/<category_slug>')
def group_category(group_slug, category_slug='all'):
    if group_slug == 'press-centre':
        group_slug = 'canonical-announcements'

    try:
        group = local_data.get_group_by_slug(group_slug)
    except KeyError:
        flask.abort(404)

    if not group:
        flask.abort(404)

    group_details = local_data.get_group_details(group_slug)

    category = local_data.get_category_by_slug(category_slug)

    page = flask.request.args.get('page')
    posts, metadata = api.get_posts(
        groups_id=group['id'],
        categories=[category['id']] if category and category['id'] else [],
        page=page,
        per_page=12
    )

    if group_slug == 'canonical-announcements':
        return flask.render_template(
            'press-centre.html',
            posts=posts,
            group=group,
            group_details=group_details,
            category=category if category else None,
            today=datetime.utcnow(),
            **metadata
        )
    else:
        return flask.render_template(
            'group.html',
            posts=posts,
            group=group,
            group_details=group_details,
            category=category_slug if category_slug else None,
            **metadata
        )


@app.route('/topics/<slug>')
def topic_name(slug):
    topic = local_data.get_topic_details(slug)

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


@app.route('/tag/<slug>')
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


@app.route('/archives/<regex("[0-9]{4}"):year>')
def archives_year(year):
    page = flask.request.args.get('page')

    result, metadata = api.get_archives(year, page=page)
    return flask.render_template(
        'archives.html',
        result=result,
        today=datetime.utcnow(),
        **metadata
    )


@app.route('/archives/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>')
def archives_year_month(year, month):
    page = flask.request.args.get('page')

    result, metadata = api.get_archives(year, month, page=page)
    return flask.render_template(
        'archives.html',
        result=result,
        today=datetime.utcnow(),
        **metadata
    )


@app.route('/archives/<group>/<regex("[0-9]{4}"):year>')
def archives_group_year(group, year):
    group_slug = group

    if group == 'press-centre':
        group = 'canonical-announcements'

    groups = api.get_group_by_slug(group)

    if not groups:
        flask.abort(404)

    group_id = int(groups['id']) if groups else None
    group_name = groups['name'] if groups else None

    result, metadata = api.get_archives(year, None, group_id, group_name)
    return flask.render_template(
        'archives.html',
        result=result,
        group=group_slug,
        today=datetime.utcnow(),
        **metadata
    )


@app.route(
    '/archives/<group>/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>'
)
def archives_group_year_month(group, year, month):
    page = flask.request.args.get('page')
    if group == 'press-centre':
        group = 'canonical-announcements'

    groups = local_data.get_group_by_slug(group)
    if not groups:
        flask.abort(404)

    group_id = int(groups['id']) if groups else None
    group_name = groups['name'] if groups else None

    result, metadata = api.get_archives(
        year,
        month,
        group_id,
        group_name,
        page=page
    )

    return flask.render_template(
        'archives.html',
        result=result,
        **metadata
    )


@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<regex("[0-9]{2}"):day>'
    '/<slug>'
)
def post(year, month, day, slug):
    return flask.render_template('post.html', post=api.get_post(slug))


@app.route('/author/<slug>')
def user(slug):
    return flask.render_template('author.html', author=api.get_author(slug))


@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404


@app.errorhandler(410)
def page_deleted(e):
    return flask.render_template('410.html'), 410


@app.errorhandler(500)
def server_error(e):
    return flask.render_template('500.html'), 500
