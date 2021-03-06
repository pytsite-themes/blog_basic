"""Theme Controllers
"""
from typing import Dict as _Dict
from datetime import datetime, timedelta
from pytsite import tpl, odm, lang, settings, auth_profile, plugman, routing
from plugins import content, section, tag, comments
from app import model

__author__ = 'Alexander Shepetko'
__email__ = 'a@shepetko.com'
__license__ = 'MIT'


class Home(routing.Controller):
    """Home
    """

    def exec(self) -> str:
        exclude_ids = []

        latest = _get_articles(exclude_ids, 3)

        sections = list(section.get())
        latest_by_section = {}
        for sec in sections:
            latest_by_section[sec.alias] = _get_articles(exclude_ids, 4, sec=sec)

        tpl_args = {
            'sections': sections,
            'latest_articles': latest,
            'latest_by_section': latest_by_section,
            'sidebar': _get_sidebar(exclude_ids),
        }

        return tpl.render('home', tpl_args)


class ContentEntityIndex(routing.Controller):
    """Content entity index
    """

    def exec(self) -> str:
        self.args.update(content.paginate(self.arg('finder')))

        exclude_ids = [e.id for e in self.arg('entities')]
        self.args.update({
            'sidebar': _get_sidebar(exclude_ids),
        })

        author = self.arg('author')
        if author:
            self.args['author_widget'] = auth_profile.widget.Profile('user-profile', user=author)

        return tpl.render('$theme@content/index', self.args)


class ContentEntityView(routing.Controller):
    """Content entity view
    """

    def exec(self) -> str:

        e = self.arg('entity')
        exclude_ids = [e.id]

        self.args.update({
            'related': _get_articles(exclude_ids, 3, e.section, 'views_count') if e.model == 'article' else [],
            'entity_tags': tag.widget.EntityTagCloud('entity-tag-cloud', entity=e),
            'sidebar': _get_sidebar(exclude_ids),
        })

        if plugman.is_installed('addthis'):
            from plugins import addthis
            self.args.update({
                'share_widget': addthis.widget.AddThis('add-this-share') if settings.get('addthis.pub_id') else '',
            })

        if plugman.is_installed('disqus'):
            self.args.update({
                'comments_widget': comments.get_widget(driver_name='disqus')
            })

        return tpl.render('content/{}'.format(e.model), self.args)


def _get_sidebar(exclude_ids: list) -> _Dict:
    """Get sidebar content
    """
    r = {
        'popular': _get_articles(exclude_ids, 3, sort_field='views_count', days=30),
        'latest': _get_articles(exclude_ids, 3, days=30),
        'tag_cloud': tag.widget.TagCloud(
            uid='sidebar-tag-cloud',
            title=lang.t('tags_cloud'),
            css='block',
            term_css='hvr-sweep-to-right',
        ),
    }

    if plugman.is_installed('content_digest'):
        from plugins import content_digest
        r['content_digest_subscribe'] = content_digest.widget.Subscribe()

    return r


def _get_articles(exclude_ids: list, count: int = 6, sec: section.model.Section = None,
                  sort_field: str = 'publish_time', days: int = None, starred: bool = False) -> list:
    """Get articles
    """
    # Setup articles finder
    f = content.find('article').ninc('_id', exclude_ids).sort([(sort_field, odm.I_DESC)])

    # Filter by section
    if sec:
        f.eq('section', sec)

    # Filter by publish time
    if days:
        # Determine last published article date
        last_article = content.find('article').sort([('publish_time', odm.I_DESC)]).first()  # type: model.Article
        if last_article:
            f.gte('publish_time', last_article.publish_time - timedelta(days))
        else:
            f.gte('publish_time', datetime.now() - timedelta(days))

    # Filter by 'starred' flag
    if starred:
        f.eq('starred', True)

    r = []
    for article in f.get(count):
        # Show only articles which can be viewed by current user
        if article.odm_auth_check_permission('view') or article.odm_auth_check_permission('view_own'):
            r.append(article)
        exclude_ids.append(article.id)

    return r
