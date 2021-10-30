# coding: utf-8
from __future__ import unicode_literals

import re
import itertools

from .common import InfoExtractor
from ..compat import (
    compat_str,
    compat_parse_qs,
    compat_urllib_parse_urlparse,
    compat_urllib_parse_urlencode,
)
from ..utils import (
    determine_ext,
    bool_or_none,
    int_or_none,
    try_get,
    unified_timestamp,
    url_or_none,
    smuggle_url,
    unsmuggle_url,
    unescapeHTML,
)


class GlomexBaseIE(InfoExtractor):
    _DEFAULT_ORIGIN_URL = 'https://player.glomex.com/'
    _BASE_API_URL = 'https://integration-cloudfront-eu-west-1.mes.glomex.cloud/'

    @staticmethod
    def _smuggle_origin_url(url, origin_url):
        return smuggle_url(url, {'origin': origin_url})

    @classmethod
    def _unsmuggle_origin_url(cls, url, fallback_origin_url=None):
        defaults = {'origin': fallback_origin_url or cls._DEFAULT_ORIGIN_URL}
        unsmuggled_url, data = unsmuggle_url(url, default=defaults)
        return unsmuggled_url, data['origin']

    def _download_api_data(self, video_id, integration, current_url=None):
        query = {
            'integration_id': integration,
            'playlist_id': video_id,
            'current_url': current_url or self._DEFAULT_ORIGIN_URL,
        }
        return self._download_json(
            self._BASE_API_URL,
            video_id, 'Downloading video JSON',
            'Unable to download video JSON', query=query)

    @staticmethod
    def _extract_info(_video, video_id=None, require_title=True):
        video = _video['videos'][0]

        title = video['title'] if require_title else video.get('title')

        thumbnail = '%s/profile:player-960x540' % try_get(
            video, lambda x: x['image']['url'])

        return {
            'id': video.get('clip_id') or video_id,
            'title': title,
            'description': video.get('description'),
            'thumbnail': thumbnail,
            'duration': int_or_none(video.get('clip_duration')),
            'timestamp': video.get('created_at'),
        }

    def _download_and_extract_api_data(self, video_id, integration, current_url):
        api_data = self._download_api_data(video_id, integration, current_url)
        info = self._extract_info(api_data, video_id)
        info['formats'] = self._extract_formats(api_data, video_id)
        return info

    def _extract_formats(self, _options, video_id):
        options = _options['videos'][0]
        formats = []
        for format_id, format_url in options['source'].items():
            ext = determine_ext(format_url)
            if ext == 'm3u8':
                formats.extend(self._extract_m3u8_formats(
                    format_url, video_id, 'mp4', m3u8_id=format_id,
                    fatal=False))
            else:
                formats.append({
                    'url': format_url,
                    'format_id': format_id,
                })
        self._sort_formats(formats)
        return formats


class GlomexIE(GlomexBaseIE):
    IE_NAME = 'glomex'
    IE_DESC = 'Glomex videos'
    _VALID_URL = r'https?://video.glomex.com/[^/]+/(?P<id>v-[^-]+)'
    # Hard-coded integration ID for video.glomex.com
    _INTEGRATION_ID = '19syy24xjn1oqlpc'

    _TESTS = [{
        'url': 'http://rutube.ru/video/3eac3b4561676c17df9132a9a1e62e3e/',
        'md5': '1d24f180fac7a02f3900712e5a5764d6',
        'info_dict': {
            'id': '3eac3b4561676c17df9132a9a1e62e3e',
            'ext': 'mp4',
            'title': 'Раненный кенгуру забежал в аптеку',
            'description': 'http://www.ntdtv.ru ',
            'duration': 81,
            'uploader': 'NTDRussian',
            'uploader_id': '29790',
            'timestamp': 1381943602,
            'upload_date': '20131016',
            'age_limit': 0,
        },
    }, {
        'url': 'http://rutube.ru/play/embed/a10e53b86e8f349080f718582ce4c661',
        'only_matching': True,
    }, {
        'url': 'http://rutube.ru/embed/a10e53b86e8f349080f718582ce4c661',
        'only_matching': True,
    }, {
        'url': 'http://rutube.ru/video/3eac3b4561676c17df9132a9a1e62e3e/?pl_id=4252',
        'only_matching': True,
    }, {
        'url': 'https://rutube.ru/video/10b3a03fc01d5bbcc632a2f3514e8aab/?pl_type=source',
        'only_matching': True,
    }]

    @classmethod
    def suitable(cls, url):
        return False if GlomexPlaylistIE.suitable(url) else super(GlomexIE, cls).suitable(url)

    def _real_extract(self, url):
        video_id = self._match_id(url)
        # Defer to the glomex:embed IE: Build and return a player URL using the
        # matched video ID and the hard-coded integration ID
        return {
            '_type': 'url',
            'url': GlomexEmbedIE.build_player_url(video_id,
                self._INTEGRATION_ID, url),
            'ie_key': GlomexEmbedIE.ie_key(),
        }


class GlomexEmbedIE(GlomexBaseIE):
    IE_NAME = 'glomex:embed'
    IE_DESC = 'Glomex embedded videos'
    _BASE_PLAYER_URL = 'https://player.glomex.com/integration/1/iframe-player.html'
    _VALID_URL = r'(?:https?:)?//player\.glomex\.com/integration/[^/]+/iframe-player\.html\?(?:(?:integrationId=(?P<integration>[^&#]+)|playlistId=(?P<id>[^&#]+)|[^&=#]+=[^&#]+)&?)+'

    _TESTS = [{
        'url': 'http://rutube.ru/video/embed/6722881?vk_puid37=&vk_puid38=',
        'info_dict': {
            'id': 'a10e53b86e8f349080f718582ce4c661',
            'ext': 'mp4',
            'timestamp': 1387830582,
            'upload_date': '20131223',
            'uploader_id': '297833',
            'description': 'Видео группы ★http://vk.com/foxkidsreset★ музей Fox Kids и Jetix<br/><br/> восстановлено и сделано в шикоформате subziro89 http://vk.com/subziro89',
            'uploader': 'subziro89 ILya',
            'title': 'Мистический городок Эйри в Индиан 5 серия озвучка subziro89',
        },
        'params': {
            'skip_download': True,
        },
    }, {
        'url': 'http://rutube.ru/play/embed/8083783',
        'only_matching': True,
    }, {
        # private video
        'url': 'https://rutube.ru/play/embed/10631925?p=IbAigKqWd1do4mjaM5XLIQ',
        'only_matching': True,
    }]

    @classmethod
    def build_player_url(cls, video_id, integration, origin_url=None):
        query_string = compat_urllib_parse_urlencode({
            'playlistId': video_id,
            'integrationId': integration,
        })
        player_url = '%s?%s' % (cls._BASE_PLAYER_URL, query_string)
        if origin_url is not None:
            player_url = cls._smuggle_origin_url(player_url, origin_url)
        return player_url

    @classmethod
    def _match_integration(cls, url):
        if '_VALID_URL_RE' not in cls.__dict__:
            cls._VALID_URL_RE = re.compile(cls._VALID_URL)
        m = cls._VALID_URL_RE.match(url)
        assert m
        return compat_str(m.group('integration'))

    @classmethod
    def _extract_urls(cls, webpage, origin_url):
        # https://docs.glomex.com/publisher/video-player-integration/javascript-api/
        EMBED_RE = r'''(?x)
        (?:
            <iframe[^>]+?src=(?P<_q1>%(quot_re)s)
                (?P<url>(?:https?:)?//player\.glomex\.com/integration/[^/]+/iframe-player\.html\?
                (?:(?!(?P=_q1)).)+)(?P=_q1)|
            <(?P<html_tag>glomex-player|div)(?:
                data-integration-id=(?P<_q2>%(quot_re)s)(?P<integration_html>(?:(?!(?P=_q2)).)+)(?P=_q2)|
                data-playlist-id=(?P<_q3>%(quot_re)s)(?P<id_html>(?:(?!(?P=_q3)).)+)(?P=_q3)|
                data-glomex-player=(?P<_q4>%(quot_re)s)(?P<glomex_player>true)(?P=_q4)|
                [^>]*?
            )+>|
            # naive parsing of inline scripts for hard-coded integration parameters
            <(?P<script_tag>script)[^<]*?>(?:
                (?P<_stjs1>dataset\.)?integrationId\s*(?(_stjs1)=|:)\s*
                    (?P<_q5>%(quot_re)s)(?P<integration_js>(?:(?!(?P=_q5)).)+)(?P=_q5)\s*(?(_stjs1);|,)?|
                (?P<_stjs2>dataset\.)?playlistId\s*(?(_stjs2)=|:)\s*
                    (?P<_q6>%(quot_re)s)(?P<id_js>(?:(?!(?P=_q6)).)+)(?P=_q6)\s*(?(_stjs2);|,)?|
                (?:\s|.)*?
            )+</script>
        )
        ''' % { 'quot_re': r'[\"\']' }
        for mobj in re.finditer(EMBED_RE, webpage):
            url, html_tag, video_id_html, integration_html, glomex_player, \
                script_tag, video_id_js, integration_js = \
                    mobj.group('url', 'html_tag', 'id_html',
                        'integration_html', 'glomex_player', 'script_tag',
                        'id_js', 'integration_js')
            if url:
                yield cls._smuggle_origin_url(unescapeHTML(url), origin_url)
            elif html_tag:
                if html_tag == "div" and not glomex_player:
                    continue
                if not video_id_html or not integration_html:
                    continue
                yield cls.build_player_url(video_id_html, integration_html, url)
            elif script_tag:
                if not video_id_js or not integration_js:
                    continue
                yield cls.build_player_url(video_id_js, integration_js, url)

    def _real_extract(self, url):
        url, origin_url = self._unsmuggle_origin_url(url)
        embed_id = self._match_id(url)
        query = compat_parse_qs(compat_urllib_parse_urlparse(url).query)
        video_id = query['playlistId'][0]
        integration = query['integrationId'][0]
        return self._download_and_extract_api_data(video_id, integration, origin_url)


class RutubePlaylistBaseIE(RutubeBaseIE):
    def _next_page_url(self, page_num, playlist_id, *args, **kwargs):
        return self._PAGE_TEMPLATE % (playlist_id, page_num)

    def _entries(self, playlist_id, *args, **kwargs):
        next_page_url = None
        for pagenum in itertools.count(1):
            page = self._download_json(
                next_page_url or self._next_page_url(
                    pagenum, playlist_id, *args, **kwargs),
                playlist_id, 'Downloading page %s' % pagenum)

            results = page.get('results')
            if not results or not isinstance(results, list):
                break

            for result in results:
                video_url = url_or_none(result.get('video_url'))
                if not video_url:
                    continue
                entry = self._extract_info(result, require_title=False)
                entry.update({
                    '_type': 'url',
                    'url': video_url,
                    'ie_key': RutubeIE.ie_key(),
                })
                yield entry

            next_page_url = page.get('next')
            if not next_page_url or not page.get('has_next'):
                break

    def _extract_playlist(self, playlist_id, *args, **kwargs):
        return self.playlist_result(
            self._entries(playlist_id, *args, **kwargs),
            playlist_id, kwargs.get('playlist_name'))

    def _real_extract(self, url):
        return self._extract_playlist(self._match_id(url))


class RutubeChannelIE(RutubePlaylistBaseIE):
    IE_NAME = 'rutube:channel'
    IE_DESC = 'Rutube channels'
    _VALID_URL = r'https?://rutube\.ru/tags/video/(?P<id>\d+)'
    _TESTS = [{
        'url': 'http://rutube.ru/tags/video/1800/',
        'info_dict': {
            'id': '1800',
        },
        'playlist_mincount': 68,
    }]

    _PAGE_TEMPLATE = 'http://rutube.ru/api/tags/video/%s/?page=%s&format=json'


class RutubeMovieIE(RutubePlaylistBaseIE):
    IE_NAME = 'rutube:movie'
    IE_DESC = 'Rutube movies'
    _VALID_URL = r'https?://rutube\.ru/metainfo/tv/(?P<id>\d+)'
    _TESTS = []

    _MOVIE_TEMPLATE = 'http://rutube.ru/api/metainfo/tv/%s/?format=json'
    _PAGE_TEMPLATE = 'http://rutube.ru/api/metainfo/tv/%s/video?page=%s&format=json'

    def _real_extract(self, url):
        movie_id = self._match_id(url)
        movie = self._download_json(
            self._MOVIE_TEMPLATE % movie_id, movie_id,
            'Downloading movie JSON')
        return self._extract_playlist(
            movie_id, playlist_name=movie.get('name'))


class RutubePersonIE(RutubePlaylistBaseIE):
    IE_NAME = 'rutube:person'
    IE_DESC = 'Rutube person videos'
    _VALID_URL = r'https?://rutube\.ru/video/person/(?P<id>\d+)'
    _TESTS = [{
        'url': 'http://rutube.ru/video/person/313878/',
        'info_dict': {
            'id': '313878',
        },
        'playlist_mincount': 37,
    }]

    _PAGE_TEMPLATE = 'http://rutube.ru/api/video/person/%s/?page=%s&format=json'


class RutubePlaylistIE(RutubePlaylistBaseIE):
    IE_NAME = 'rutube:playlist'
    IE_DESC = 'Rutube playlists'
    _VALID_URL = r'https?://rutube\.ru/(?:video|(?:play/)?embed)/[\da-z]{32}/\?.*?\bpl_id=(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://rutube.ru/video/cecd58ed7d531fc0f3d795d51cee9026/?pl_id=3097&pl_type=tag',
        'info_dict': {
            'id': '3097',
        },
        'playlist_count': 27,
    }, {
        'url': 'https://rutube.ru/video/10b3a03fc01d5bbcc632a2f3514e8aab/?pl_id=4252&pl_type=source',
        'only_matching': True,
    }]

    _PAGE_TEMPLATE = 'http://rutube.ru/api/playlist/%s/%s/?page=%s&format=json'

    @classmethod
    def suitable(cls, url):
        if not super(RutubePlaylistIE, cls).suitable(url):
            return False
        params = compat_parse_qs(compat_urllib_parse_urlparse(url).query)
        return params.get('pl_type', [None])[0] and int_or_none(params.get('pl_id', [None])[0])

    def _next_page_url(self, page_num, playlist_id, item_kind):
        return self._PAGE_TEMPLATE % (item_kind, playlist_id, page_num)

    def _real_extract(self, url):
        qs = compat_parse_qs(compat_urllib_parse_urlparse(url).query)
        playlist_kind = qs['pl_type'][0]
        playlist_id = qs['pl_id'][0]
        return self._extract_playlist(playlist_id, item_kind=playlist_kind)
