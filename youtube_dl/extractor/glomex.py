# coding: utf-8
from __future__ import unicode_literals

import re

from .common import InfoExtractor
from ..compat import (
    compat_str,
    compat_parse_qs,
    compat_urllib_parse_urlparse,
    compat_urllib_parse_urlencode,
)
from ..utils import (
    ExtractorError,
    determine_ext,
    int_or_none,
    try_get,
    smuggle_url,
    unsmuggle_url,
    unescapeHTML,
)


class GlomexBaseIE(InfoExtractor):
    _DEFAULT_ORIGIN_URL = 'https://player.glomex.com/'
    _API_URL = 'https://integration-cloudfront-eu-west-1.mes.glomex.cloud/'

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
        video_id_type = self._get_videoid_type(video_id)
        return self._download_json(
            self._API_URL,
            video_id, 'Downloading %s JSON' % video_id_type,
            'Unable to download %s JSON' % video_id_type,
            query=query)

    @staticmethod
    def _extract_info(video, video_id=None, require_title=True):
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

    def _get_videoid_type(self, video_id):
        _VIDEOID_TYPES = {
            'v':  'video',
            'pl': 'playlist',
            'rl': 'related videos playlist',
            'cl': 'curated playlist',
        }
        prefix = video_id.split('-')[0]
        return _VIDEOID_TYPES.get(prefix, 'unknown type')

    def _extract_api_data(self, video, video_id):
        if video.get('error_code') == 'contentGeoblocked':
            self.raise_geo_restricted(countries=video['geo_locations'])
        info = self._extract_info(video, video_id)
        info['formats'] = self._extract_formats(video, video_id)
        return info

    def _download_and_extract_api_data(self, video_id, integration, current_url):
        api_data = self._download_api_data(video_id, integration, current_url)
        videos = api_data['videos']
        if not videos:
            raise ExtractorError('no videos found for %s' % video_id)
        if len(videos) == 1:
            return self._extract_api_data(videos[0], video_id)
        # assume some kind of playlist
        videos = [
            self._extract_api_data(video, video_id)
            for video in videos
        ]
        playlist_title = videos[0].get('title')
        playlist_description = videos[0].get('description')
        return self.playlist_result(videos, video_id,
                                    playlist_title, playlist_description)

    def _extract_formats(self, options, video_id):
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

    def _real_extract(self, url):
        video_id = self._match_id(url)
        # Defer to the glomex:embed IE: Build and return a player URL using the
        # matched video ID and the hard-coded integration ID
        return self.url_result(
            GlomexEmbedIE.build_player_url(video_id, self._INTEGRATION_ID,
                                           url),
            GlomexEmbedIE.ie_key(),
            video_id
        )


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
        ''' % {'quot_re': r'[\"\']'}
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
        # perhaps redundant
        assert embed_id == video_id
        integration = query['integrationId'][0]
        return self._download_and_extract_api_data(video_id, integration, origin_url)
