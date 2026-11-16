import json
import re
import struct
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = []
        self.references = []
        self.nav = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'data-nav' in attrs:
            self.nav.append((attrs['data-nav'], attrs['href']))
        for attr in ('src', 'href'):
            if attrs.get(attr):
                self.references.append(attrs[attr])


@pytest.mark.parametrize('filename', ['index.html', 'browse.html', 'market.html'])
def test_page_assets_and_unique_ids(filename):
    page = Page((ROOT / filename).read_text(encoding='utf-8'))
    assert len(page.ids) == len(set(page.ids))
    for reference in page.references:
        url = urlsplit(reference)
        if not url.scheme and not reference.startswith('#'):
            assert (ROOT / url.path).is_file(), reference
    assert page.nav == [('today', './index.html'), ('browse', './browse.html'), ('market', './market.html')]


def test_market_has_six_complete_chart_sections():
    page = Page((ROOT / 'market.html').read_text(encoding='utf-8'))
    for key in ['new', 'removed', 'employers', 'duration', 'share', 'locations']:
        assert all(f'{prefix}-{key}' in page.ids for prefix in ['finding', 'explain', 'chart'])


@pytest.mark.parametrize('size', [192, 512])
def test_manifest_icons_are_real_pngs(size):
    image = (ROOT / f'assets/icon-{size}.png').read_bytes()
    assert image[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('!II', image[16:24]) == (size, size)


def test_install_manifest_works_under_repository_subpath():
    manifest = json.loads((ROOT / 'manifest.webmanifest').read_text(encoding='utf-8-sig'))
    assert manifest['scope'] == './'
    assert manifest['start_url'] == './index.html'
    assert manifest['display'] == 'standalone'
    assert {icon['sizes'] for icon in manifest['icons']} == {'192x192', '512x512'}
    for icon in manifest['icons']:
        assert (ROOT / icon['src']).is_file()


def test_all_precached_assets_exist():
    script = (ROOT / 'sw.js').read_text(encoding='utf-8')
    shell = re.search(r'const SHELL = \[(.*?)\];', script).group(1)
    for reference in re.findall(r"'([^']+)'", shell):
        path = ROOT / urlsplit(reference).path
        assert path.exists(), reference
