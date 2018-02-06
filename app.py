# Core
from datetime import datetime
from urllib.parse import urlparse, urlunparse, unquote

# Third-party
import flask
from dateutil.relativedelta import relativedelta

# Local
import api
import local_data
import helpers
import redirects


INSIGHTS_URL = 'https://insights.ubuntu.com'

app = flask.Flask(__name__)
app.jinja_env.filters['monthname'] = helpers.monthname
app.url_map.strict_slashes = False
app.url_map.converters['regex'] = helpers.RegexConverter

apply_redirects = redirects.prepare_redirects(
    permanent_redirects_path='permanent-redirects.yaml',
    redirects_path='redirects.yaml'
)
app.before_request(apply_redirects)


def page_links(page, total_pages):
    pagination_start = page - 2
    if pagination_start <= 1:
        pagination_start = 1

    if total_pages - pagination_start < 5 and pagination_start > 3:
        pagination_start = total_pages - 4


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
    posts, total_posts, total_pages = api.get_posts(per_page=13)

    sticky_posts, sticky_total, sticky_pages = api.get_posts(sticky=True)
    featured_post = sticky_posts[0] if sticky_posts else None

    if featured_post:
        posts.remove(featured_post)
        featured_post = helpers.format_post(featured_post)
        featured_post['group'] = helpers.get_first_group(
            featured_post['group']
        )
        featured_post['category'] = helpers.get_first_category(
            featured_post['categories']
        )

    # Format posts as we need them
    for post in posts:
        post = helpers.format_post(post)
        post['group'] = helpers.get_first_group(post['group'])
        post['category'] = helpers.get_first_category(post['categories'])

    return flask.render_template(
        'index.html',
        posts=posts[:12],
        featured_post=featured_post,
        webinars=helpers.get_rss_feed_content(
            'https://www.brighttalk.com/channel/6793/feed'
        )
    )


@app.route(
    '/<regex(\
        "(videos|white-papers|case-studies|webinars|articles)"\
    ):category_slug>'
)
def category(category_slug):
    page = helpers.to_int(flask.request.args.get('page'), default=1)
    categories = api.get_categories(slugs=[category_slug])

    if not categories:
        flask.abort('404')

    category = categories[0]

    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        category_ids=[category['id']] if category and category['id'] else [],
        page=page,
        per_page=12
    )

    return flask.render_template(
        'category.html',
        posts=posts,
        category=category,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
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
        group=group,
        group_details=local_data.get_group_details(group['slug']),
        current_year=datetime.now().year
    )


@app.route('/<group_slug>')
@app.route('/<group_slug>/<category_slug>')
def group_category(group_slug, category_slug=''):
    page = int(flask.request.args.get('page') or '1')
    groups = api.get_groups(slugs=[group_slug])
    category = None

    if not groups:
        flask.abort(404)

    group = groups[0]

    if category_slug:
        categories = api.get_categories(slugs=[category_slug])

        if not categories:
            flask.abort(404)

        category = categories[0]

    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        group_ids=[group['id']],
        category_ids=[category['id']] if category else [],
        page=page,
        per_page=12
    )

    return flask.render_template(
        'group.html',
        posts=posts,
        group=group,
        group_details=local_data.get_group_details(group_slug),
        category=category if category_slug else None,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
    )


@app.route('/topics/<slug>')
def topic_name(slug):
    page = helpers.to_int(flask.request.args.get('page'), default=1)
    topic = local_data.get_topic_details(slug)
    tags = api.get_tags(slugs=[slug])

    if not topic or not tags:
        flask.abort(404)

    tag = tags[0]
    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        tag_ids=[tag['id']], page=page
    )

    return flask.render_template(
        'topics.html',
        topic=topic,
        posts=posts,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
    )


@app.route('/tag/<slug>')
def tag(slug):
    page = helpers.to_int(flask.request.args.get('page'), default=1)
    tags = api.get_tags(slugs=[slug])

    if not tags:
        flask.abort(404)

    tag = tags[0]
    posts, total_posts, total_pages = helpers.get_formatted_expanded_posts(
        tag_ids=[tag['id']], page=page
    )

    return flask.render_template(
        'tag.html',
        posts=posts,
        tag=tag,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
    )


@app.route('/archives')
def archives():
    page = helpers.to_int(flask.request.args.get('page'), default=1)
    year = helpers.to_int(flask.request.args.get('year'))
    month = helpers.to_int(flask.request.args.get('month'))
    group_slug = flask.request.args.get('group')

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

    posts, total_posts, total_pages = helpers.get_formatted_posts(
        page=page,
        after=after,
        before=before,
        group_ids=[group['id']] if group else [],
    )

    return flask.render_template(
        'archives.html',
        posts=posts,
        group=group,
        current_page=page,
        total_posts=total_posts,
        total_pages=total_pages,
        friendly_date=friendly_date,
        now=datetime.now(),
    )


@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<regex("[0-9]{2}"):day>'
    '/<slug>'
)
def post(year, month, day, slug):
    posts, total_posts, total_pages = helpers.get_formatted_posts(slugs=[slug])

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
