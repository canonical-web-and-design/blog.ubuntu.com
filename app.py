# Core
import calendar
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
    page = int(flask.request.args.get('page', '1'))
    posts, metadata = api.get_posts(page=page, per_page=13)

    webinars = helpers.get_rss_feed_content(
        'https://www.brighttalk.com/channel/6793/feed'
    )
    page_slug = ''

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
        page_slug=page_slug,
        **metadata
    )


@app.route(
    '/<regex(\
        "(videos|whitepapers|case-studies|webinars|articles)"\
    ):category_slug>'
)
def category(category_slug):
    category = local_data.get_category_by_slug(category_slug)
    page_slug = category_slug

    page = int(flask.request.args.get('page', '1'))
    posts, metadata = api.get_posts(
        categories=[category['id']] if category and category['id'] else [],
        page=page,
        per_page=12
    )

    return flask.render_template(
        'category.html',
        posts=posts,
        category=category_slug,
        page_slug=page_slug,
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


@app.route('/press-centre')
def press_centre():
    group = local_data.get_group_by_slug('canonical-announcements')
    group_details = local_data.get_group_details('canonical-announcements')
    page_slug = 'press-centre'

    posts, metadata = api.get_posts(groups_id=group['id'], per_page=12)

    return flask.render_template(
        'press-centre.html',
        posts=posts,
        group=group,
        group_details=group_details,
        page_slug=page_slug,
        today=datetime.utcnow(),
    )


@app.route('/<group_slug>')
@app.route('/<group_slug>/<category_slug>')
def group_category(group_slug, category_slug=''):
    try:
        group = local_data.get_group_by_slug(group_slug)
        group_details = local_data.get_group_details(group_slug)
    except KeyError:
        flask.abort(404)

    category_ids = []
    page_slug = group_slug

    if category_slug:
        try:
            category_ids = [
                local_data.get_category_by_slug(category_slug)['id']
            ]
        except KeyError:
            flask.abort(404)

    page = int(flask.request.args.get('page', '1'))

    posts, metadata = api.get_posts(
        groups_id=group['id'],
        categories=category_ids,
        page=page,
        per_page=12
    )

    return flask.render_template(
        'group.html',
        posts=posts,
        group=group,
        group_details=group_details,
        page_slug=page_slug,
        category=category_slug if category_slug else None,
        **metadata
    )


@app.route('/topics/<slug>')
def topic_name(slug):
    topic = local_data.get_topic_details(slug)
    page_slug = 'topics'

    if not topic:
        flask.abort(404)

    tags = api.get_tag(slug=topic['slug'])

    if not tags:
        flask.abort(404)

    if tags:
        tag = tags[0]
        page = int(flask.request.args.get('page', '1'))
        posts, metadata = api.get_posts(tags=[tag['id']], page=page)

    return flask.render_template(
        'topics.html',
        topic=topic,
        posts=posts,
        page_slug=page_slug,
        **metadata
    )


@app.route('/tag/<slug>')
def tag_index(slug):
    response_json = api.get_tag(slug)
    page_slug = 'tag'

    if not response_json:
        flask.abort(404)

    tag = response_json[0]
    page = int(flask.request.args.get('page', '1'))
    posts, metadata = api.get_posts(tags=[tag['id']], page=page)

    return flask.render_template(
        'tag.html',
        posts=posts,
        tag=tag,
        page_slug=page_slug,
        **metadata
    )


@app.route('/archives/<regex("[0-9]{4}"):year>')
def archives_year(year):
    page = int(flask.request.args.get('page', '1'))
    page_slug = 'archives'

    result, metadata = api.get_archives(year, page=page)
    return flask.render_template(
        'archives.html',
        result=result,
        page_slug=page_slug,
        today=datetime.utcnow(),
        **metadata
    )


@app.route('/archives/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>')
def archives_year_month(year, month):
    page = int(flask.request.args.get('page', '1'))
    page_slug = 'archives'

    try:
        result, metadata = api.get_archives(year, month, page=page)
    except calendar.IllegalMonthError:
        flask.abort(404)

    return flask.render_template(
        'archives.html',
        result=result,
        page_slug=page_slug,
        today=datetime.utcnow(),
        **metadata
    )


@app.route('/archives/<group>/<regex("[0-9]{4}"):year>')
def archives_group_year(group, year):
    group_slug = group
    page_slug = 'archives'

    if group == 'press-centre':
        group = 'canonical-announcements'

    try:
        groups = local_data.get_group_by_slug(group)
    except KeyError:
        flask.abort(404)

    if not groups:
        flask.abort(404)

    group_id = int(groups['id']) if groups else None
    group_name = groups['name'] if groups else None

    result, metadata = api.get_archives(year, None, group_id, group_name)
    return flask.render_template(
        'archives.html',
        result=result,
        group=group_slug,
        page_slug=page_slug,
        today=datetime.utcnow(),
        **metadata
    )


@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<regex("[0-9]{2}"):day>'
    '/<slug>'
)
def post(year, month, day, slug):
    page_slug = 'archives'
    try:
        post = api.get_post(slug)
    except IndexError:
        flask.abort(404)

    return flask.render_template('post.html', page_slug=page_slug, post=post)


@app.route('/author/<slug>')
def user(slug):
    page_slug = 'author'
    try:
        author = api.get_author(slug)
    except IndexError:
        flask.abort(404)

    return flask.render_template(
        'author.html',
        page_slug=page_slug,
        author=author
    )


@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404


@app.errorhandler(410)
def page_deleted(e):
    return flask.render_template('410.html'), 410


@app.errorhandler(500)
def server_error(e):
    return flask.render_template('500.html'), 500
