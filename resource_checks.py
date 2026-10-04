#!/usr/bin/env python3
"""Find non-embedded resource URLs in HTML/CSS for single-file book builds.

A saved book is self-contained only when resource-bearing references are data
URLs or same-document fragments. Relative paths are rejected too: they depend
on another file being shipped alongside the HTML.
"""

import re
from html import unescape
from html.parser import HTMLParser


_RESOURCE_ATTRIBUTES = {
    "script": ("src",),
    "link": ("href",),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "audio": ("src",),
    "video": ("src", "poster"),
    "track": ("src",),
    "iframe": ("src",),
    "frame": ("src",),
    "embed": ("src",),
    "object": ("data",),
    "input": ("src",),
    "image": ("href", "xlink:href"),
    "feimage": ("href", "xlink:href"),
    "use": ("href", "xlink:href"),
    "base": ("href",),
}

_CSS_URL_RE = re.compile(
    r"""url\(\s*(?:(['\"])(.*?)\1|([^)]*?))\s*\)""",
    re.I | re.S,
)
_CSS_IMPORT_RE = re.compile(
    r"""@import\s+(?:url\(\s*)?(?:(['\"])(.*?)\1|([^\s);]+))""",
    re.I | re.S,
)
_CSS_IMAGE_SET_RE = re.compile(r"(?:-webkit-)?image-set\((.*?)\)", re.I | re.S)
_CSS_QUOTED_URL_RE = re.compile(r"(['\"])(.*?)\1", re.S)
_REFRESH_URL_RE = re.compile(
    r"url\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^;\s]+))", re.I
)


def _embedded_or_fragment(value):
    """Whether a URL is self-contained in this HTML document."""
    url = unescape(str(value or "")).strip().strip("\"'")
    lower = url.lower()
    return not url or url.startswith("#") or lower.startswith("data:") or lower == "about:blank"


def _srcset_urls(value):
    """Yield URL tokens from srcset, treating commas inside data URLs as data."""
    text = str(value or "")
    index = 0
    while index < len(text):
        while index < len(text) and (text[index].isspace() or text[index] == ","):
            index += 1
        if index >= len(text):
            break
        start = index
        is_data = text[index:index + 5].lower() == "data:"
        if is_data:
            while index < len(text) and not text[index].isspace():
                index += 1
        else:
            while index < len(text) and not text[index].isspace() and text[index] != ",":
                index += 1
        url = text[start:index].strip()
        if url:
            yield url
        # Skip the optional width/density descriptor up to the next candidate.
        while index < len(text) and text[index] != ",":
            index += 1
        if index < len(text):
            index += 1


def parse_start_tag_attributes(tag_source):
    """Parse attributes from one start tag, including spaces around '='."""
    class AttributeParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.attributes = {}

        def handle_starttag(self, _tag, attrs):
            self.attributes = {name.lower(): value for name, value in attrs if name}

        def handle_startendtag(self, _tag, attrs):
            self.attributes = {name.lower(): value for name, value in attrs if name}

    parser = AttributeParser()
    try:
        parser.feed(tag_source)
        parser.close()
    except Exception:
        return {}
    return parser.attributes


class _ResourceScanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references = []
        self._style_depth = 0

    def _record(self, tag, attribute, value):
        url = unescape(str(value or "")).strip().strip("\"'")
        if not _embedded_or_fragment(url):
            self.references.append("<%s> %s: %s" % (tag, attribute, url))

    def _scan_css(self, css, tag, attribute):
        # Ignore comments so documentation snippets do not look like live URLs.
        css = re.sub(r"/\*.*?\*/", "", css or "", flags=re.S)
        found = set()
        for pattern in (_CSS_URL_RE, _CSS_IMPORT_RE):
            for match in pattern.finditer(css):
                url = match.group(2) if match.group(1) else match.group(3)
                if url:
                    found.add(url.strip())
        # CSS image-set() accepts bare string URLs in addition to url(...).
        for match in _CSS_IMAGE_SET_RE.finditer(css):
            for quoted in _CSS_QUOTED_URL_RE.finditer(match.group(1)):
                found.add(quoted.group(2).strip())
        for url in sorted(found):
            self._record(tag, attribute, url)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attributes = {name.lower(): value for name, value in attrs if name}
        for attribute in _RESOURCE_ATTRIBUTES.get(tag, ()):
            value = attributes.get(attribute)
            if value is None:
                continue
            if attribute == "srcset":
                for url in _srcset_urls(value):
                    self._record(tag, attribute, url)
            else:
                self._record(tag, attribute, value)

        if tag == "meta" and attributes.get("http-equiv", "").lower() == "refresh":
            content = attributes.get("content", "")
            match = _REFRESH_URL_RE.search(content)
            if match:
                self._record(tag, "refresh", next(value for value in match.groups() if value))

        if attributes.get("style"):
            self._scan_css(attributes["style"], tag, "style")
        if tag == "style":
            self._style_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() == "style" and self._style_depth:
            self._style_depth -= 1

    def handle_endtag(self, tag):
        if tag.lower() == "style" and self._style_depth:
            self._style_depth -= 1

    def handle_data(self, data):
        if self._style_depth:
            self._scan_css(data, "style", "CSS")


def external_resource_references(source):
    """Return non-embedded resource references in HTML or CSS.

    Ordinary outbound anchors are intentionally ignored; resource-bearing
    elements, CSS URLs/imports, relative file dependencies, and network URLs
    are reported. A data URI or same-document fragment is permitted.
    """
    scanner = _ResourceScanner()
    try:
        scanner.feed(source or "")
        scanner.close()
    except Exception:
        # A malformed source should not silently pass an offline-resource check.
        return ["could not parse HTML resource references"]
    return list(dict.fromkeys(scanner.references))


def is_remote_resource_url(value):
    """True for HTTP(S) and protocol-relative resource URLs."""
    url = unescape(str(value or "")).strip().strip("\"'")
    return bool(re.match(r"^(?:https?:)?//", url, re.I))
