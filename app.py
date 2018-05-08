# Core
import dateutil.parser
from datetime import datetime
from urllib.parse import urlparse, urlunparse, unquote

# Third-party
import flask
import prometheus_flask_exporter
from dateutil.relativedelta import relativedelta

# Local
import api
import feeds
import helpers
import redirects


INSIGHTS_ADMIN_URL = 'https://admin.insights.ubuntu.com'

app = flask.Flask(__name__)
app.jinja_env.filters['monthname'] = helpers.monthname
app.url_map.strict_slashes = False
app.url_map.converters['regex'] = helpers.RegexConverter

if not app.debug:
    metrics = prometheus_flask_exporter.PrometheusMetrics(
        app,
        group_by_endpoint=True,
        buckets=[0.25, 0.5, 0.75, 1, 2],
        path=None
    )
    metrics.start_http_server(port=9990, endpoint='/')

apply_redirects = redirects.prepare_redirects(
    permanent_redirects_path='permanent-redirects.yaml',
    redirects_path='redirects.yaml'
)
app.before_request(apply_redirects)


def _tag_view(tag_slug, page_slug, template):
    """
    View function which gets all posts for a given tag,
    and returns a response loading those posts with the template provided
    """

    page = helpers.to_int(flask.request.args.get('page'), default=1)
    tags = api.get_tags(slugs=[tag_slug])

    if not tags:
        flask.abort(404)

    tag = tags[0]
    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        tag_ids=[tag['id']], page=page
    )

    return flask.render_template(
        template,
        posts=posts,
        tag=tag,
        current_page=page,
        page_slug=page_slug,
        total_posts=total_posts,
        total_pages=total_pages,
    )


def _group_view(group_slug, page_slug, template):
    """
    View function which gets all posts for a given group slug,
    and returns a response loading those posts with the template provided
    """

    page = int(flask.request.args.get('page') or '1')
    category_slug = flask.request.args.get('category')

    groups = api.get_groups(slugs=[group_slug])
    category = None

    if not groups:
        flask.abort(404)

    group = groups[0]

    if category_slug:
        categories = api.get_categories(slugs=[category_slug])

        if categories:
            category = categories[0]

    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        group_ids=[group['id']],
        category_ids=[category['id']] if category else [],
        page=page,
        per_page=12
    )

    return flask.render_template(
        template,
        posts=posts,
        group=group,
        category=category if category_slug else None,
        current_page=page,
        page_slug=page_slug,
        total_posts=total_posts,
        total_pages=total_pages,
    )


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


@app.route('/status')
def status():
    """
    A simple response to test that the app is alive and working.
    This can be targeted by Kubernetes readiness and liveness checks.
    As used in snapcraft.io:
    https://github.com/canonical-websites/snapcraft.io/pull/327/files
    """

    return 'alive'


@app.route('/')
def homepage():
    category_slug = flask.request.args.get('category')

    category = None
    sticky_posts, _, _ = helpers.get_formatted_expanded_posts(sticky=True)
    featured_posts = sticky_posts[:3] if sticky_posts else None
    page = helpers.to_int(flask.request.args.get('page'), default=1)
    posts_per_page = 12

    upcoming_categories = api.get_categories(slugs=['events', 'webinars'])
    upcoming_category_ids = []

    for upcoming_category_id in upcoming_categories:
        upcoming_category_ids.append(upcoming_category_id['id'])

    upcoming_events, _, _ = helpers.get_formatted_expanded_posts(
        per_page=3,
        category_ids=upcoming_category_ids
    )

    if category_slug:
        categories = api.get_categories(slugs=[category_slug])

        if categories:
            category = categories[0]

    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        per_page=posts_per_page,
        category_ids=[category['id']] if category else [],
        page=page,
        sticky=False
    )

    return flask.render_template(
        'index.html',
        posts=posts,
        category=category,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
        featured_posts=featured_posts,
        upcoming_events=upcoming_events
    )


@app.route('/home')
def alternate_homepage():
    category_slug = flask.request.args.get('category')

    category = None
    sticky_posts, _, _ = helpers.get_formatted_expanded_posts(sticky=True)
    featured_posts = sticky_posts[:3] if sticky_posts else None
    page = helpers.to_int(flask.request.args.get('page'), default=1)
    posts_per_page = 13 if page == 1 else 12

    if category_slug:
        categories = api.get_categories(slugs=[category_slug])

        if categories:
            category = categories[0]

    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        per_page=posts_per_page,
        category_ids=[category['id']] if category else [],
        page=page
    )

    if featured_posts:
        for post in featured_posts:
            if post in posts:
                posts.remove(post)

    return flask.render_template(
        'alternate_index.html',
        posts=posts,
        category=category,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
        featured_posts=featured_posts
    )


@app.route('/search')
def search():
    query = flask.request.args.get('q') or ''
    page = helpers.to_int(flask.request.args.get('page'), default=1)
    posts = []
    total_pages = None
    total_posts = None

    if query:
        posts, total_posts, total_pages = helpers.get_formatted_posts(
            query=query, page=page
        )

    return flask.render_template(
        'search.html',
        posts=posts,
        query=query,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
    )


@app.route('/press-centre')
def press_centre():
    group = api.get_groups(slugs=['canonical-announcements'])[0]

    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        group_ids=[group['id']]
    )

    return flask.render_template(
        'press-centre.html',
        posts=posts,
        page_slug='press-centre',
        group=group,
        current_year=datetime.now().year
    )


@app.route('/cloud-and-server')
def cloud_and_server():
    return _group_view(
        page_slug='cloud-and-server',
        group_slug='cloud-and-server',
        template='cloud-and-server.html'
    )


@app.route('/internet-of-things')
def internet_of_things():
    return _group_view(
        page_slug='internet-of-things',
        group_slug='internet-of-things',
        template='internet-of-things.html'
    )


@app.route('/desktop')
def desktop():
    return _group_view(
        page_slug='desktop',
        group_slug='desktop',
        template='desktop.html'
    )


@app.route('/tag/<slug>')
def tag(slug):
    return _tag_view(
        tag_slug=slug,
        page_slug='tag',
        template='tag.html'
    )


@app.route('/topics/design')
def design():
    return _tag_view(
        tag_slug='design',
        page_slug='topics',
        template='topics/design.html'
    )


@app.route('/topics/juju')
def juju():
    return _tag_view(
        tag_slug='juju',
        page_slug='topics',
        template='topics/juju.html'
    )


@app.route('/topics/maas')
def maas():
    return _tag_view(
        tag_slug='maas',
        page_slug='topics',
        template='topics/maas.html'
    )


@app.route('/topics/snappy')
def snappy():
    return _tag_view(
        tag_slug='snappy',
        page_slug='topics',
        template='topics/snappy.html'
    )


@app.route('/archives')
def archives():
    page = helpers.to_int(flask.request.args.get('page'), default=1)
    year = helpers.to_int(flask.request.args.get('year'))
    month = helpers.to_int(flask.request.args.get('month'))
    group_slug = flask.request.args.get('group')
    category_slug = flask.request.args.get('category')

    if month and month > 12:
        month = None

    friendly_date = None
    group = None
    after = None
    before = None

    if year:
        if month:
            after = datetime(year=year, month=month, day=1)
            before = after + relativedelta(months=1)
            friendly_date = after.strftime('%B %Y')
        if not month:
            after = datetime(year=year, month=1, day=1)
            before = after + relativedelta(years=1)
            friendly_date = after.strftime('%Y')

    if group_slug:
        groups = api.get_groups(slugs=[group_slug])

        if groups:
            group = groups[0]

    if category_slug:
        categories = api.get_categories(slugs=[category_slug])
        category_ids = list(map(lambda category: category['id'], categories))
    else:
        categories = []
        category_ids = []

    posts, total_posts, total_pages = helpers.get_formatted_posts(
        page=page,
        after=after,
        before=before,
        group_ids=[group['id']] if group else [],
        category_ids=category_ids if category_ids else [],
    )

    return flask.render_template(
        'archives.html',
        posts=posts,
        group=group,
        category_slug=category_slug if category_slug else None,
        categories=categories,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
        friendly_date=friendly_date,
        now=datetime.now(),
        category_ids=category_ids
    )


@app.route('/<type>/<slug>/feed')
@app.route('/<slug>/feed')
@app.route('/feed')
def feed(type=None, slug=None): # noqa
    feed_url = ''.join([INSIGHTS_ADMIN_URL, flask.request.full_path])
    feed_text = feeds.cached_request(
        feed_url
    ).text

    feed_text = feed_text.replace(
        'admin.insights.ubuntu.com',
        'insights.ubuntu.com'
    )

    return flask.Response(feed_text, mimetype='text/xml')


@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<regex("[0-9]{2}"):day>'
    '/<slug>'
)
@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<slug>'
)
@app.route(
    '/webinar/<slug>'
)
def post(slug, year, month, day=None):
    posts, total_posts, total_pages = helpers.get_formatted_posts(slugs=[slug])

    if not day and posts:
        pubdate = dateutil.parser.parse(posts[0]['date_gmt'])
        day = pubdate.day
        return flask.redirect(
            '/{year}/{month}/{day}/{slug}'.format(**locals())
        )

    if not posts:
        flask.abort(404)

    post = posts[0]

    topics = api.get_topics(post_id=post['id'])

    if topics:
        post['topic'] = topics[0]

    tags = api.get_tags(post_id=post['id'])
    related_posts, total_posts, total_pages = helpers.get_formatted_posts(
        tag_ids=[tag['id'] for tag in tags],
        per_page=3
    )

    return flask.render_template(
        'post.html',
        post=post,
        tags=tags,
        related_posts=related_posts,
    )


@app.route('/author/<slug>')
def user(slug):
    authors = api.get_users(slugs=[slug])

    if not authors:
        flask.abort(404)

    author = authors[0]

    recent_posts, total_posts, total_pages = helpers.get_formatted_posts(
        author_ids=[author['id']],
        per_page=5
    )

    return flask.render_template(
        'author.html',
        author=author,
        recent_posts=recent_posts
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
