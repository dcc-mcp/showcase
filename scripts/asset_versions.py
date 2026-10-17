"""Content-bound browser cache versions for local CSS/JS only."""
import hashlib
import html
import os
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

LINK = re.compile(r'(?P<prefix>\b(?:src|href)=)(?P<quote>["\'])(?P<url>[^"\']+)(?P=quote)')

def version_html(text, page, sources):
    def replace(match):
        raw = html.unescape(match['url'])
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc or not parsed.path.endswith(('.js', '.css')):
            return match.group(0)
        rel = os.path.normpath(os.path.join(os.path.dirname(page), parsed.path)).replace(os.sep, '/')
        source = sources.get(rel)
        if not source:
            return match.group(0)
        with open(source, 'rb') as fh:
            version = hashlib.sha256(fh.read()).hexdigest()[:12]
        query = [(k,v) for k,v in parse_qsl(parsed.query) if k != 'v'] + [('v', version)]
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
        return match['prefix'] + match['quote'] + html.escape(url, quote=True) + match['quote']
    return LINK.sub(replace, text)


def game_revision(root, url):
    paths = [url, 'play/shell.js', 'play/shell.css']
    digest = hashlib.sha256()
    for path in paths:
        full = os.path.join(root, path)
        if os.path.isfile(full):
            with open(full, 'rb') as fh:
                digest.update(fh.read())
    return digest.hexdigest()[:12]
