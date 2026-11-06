"""Finish built pages and write the sitemap, using only the Python standard library."""
import re
import struct
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
import xml.etree.ElementTree as ET

ORIGIN = "https://jaromirsvoboda.github.io"
SIBLING_PAGES = (
    "/ai-tells/", "/ai-tells/quiz/", "/ai-tells/quiz/cs/",
    "/ai-tells/quiz/CREDITS.html", "/ai-tells/quiz/fairness.html",
    "/ai-tells/quiz/cs/CREDITS.html",
)


def image_size(path):
    """Read PNG IHDR or JPEG SOF dimensions without decoding the pixels."""
    with path.open("rb") as src:
        header = src.read(24)
        if header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
            return struct.unpack(">II", header[16:24])
        if header[:2] == b"\xff\xd8":
            src.seek(2)
            while True:
                if src.read(1) != b"\xff":
                    break
                marker = src.read(1)
                while marker == b"\xff":
                    marker = src.read(1)
                if not marker or marker in (b"\xd9", b"\xda"):
                    break
                if marker == b"\x01" or 0xD0 <= marker[0] <= 0xD7:
                    continue
                length = src.read(2)
                if len(length) != 2:
                    break
                length = int.from_bytes(length, "big")
                if length < 2:
                    break
                if 0xC0 <= marker[0] <= 0xCF and marker[0] not in (0xC4, 0xC8, 0xCC):
                    frame = src.read(5)
                    if length < 7 or len(frame) != 5:
                        break
                    height, width = struct.unpack(">HH", frame[1:])
                    return width, height
                src.seek(length - 2, 1)
    raise ValueError(f"Cannot read PNG/JPEG dimensions: {path}")


class Page(HTMLParser):
    """Patch only the tags we own, preserving MathML, scripts and all other text."""
    def __init__(self, html, path, root):
        super().__init__(convert_charrefs=False)
        self.html, self.path, self.root = html, path, root
        self.lines = [0] + [m.end() for m in re.finditer("\n", html)]
        self.edits = []
        self.images = self.headers = self.thead = 0
        self.canonical = self.og_url = None
        self.noindex = False
        self.head_end = None
        self.feed(html)
        self.close()

    def position(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def replace_tag(self, tag, attrs):
        raw = self.get_starttag_text()
        ending = " />" if raw.endswith("/>") else ">"
        text = "<" + tag + "".join(
            f' {key}="{escape(str(value), quote=True)}"' if value is not None else f" {key}"
            for key, value in attrs.items()) + ending
        start = self.position()
        self.edits.append((start, start + len(raw), text))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "canonical" in attrs.get("rel", "").split():
            self.canonical = attrs["href"]
        if tag == "meta":
            if attrs.get("property") == "og:url":
                self.og_url = attrs.get("content")
            if attrs.get("name", "").lower() == "robots":
                self.noindex = "noindex" in attrs.get("content", "").lower()
        if tag == "thead":
            self.thead += 1
        if tag == "th" and self.thead:
            attrs["scope"] = "col"
            self.headers += 1
            self.replace_tag(tag, attrs)
        if tag == "img":
            target = urlsplit(attrs["src"])
            if target.scheme or target.netloc:
                if (target.scheme not in ("", "http", "https")
                        or target.netloc != urlsplit(ORIGIN).netloc):
                    raise ValueError(f"Image must be a local PNG/JPEG: {self.path}: {attrs['src']}")
            image_path = unquote(target.path)
            base = self.root if image_path.startswith("/") else self.path.parent
            image_path = (base / image_path.lstrip("/")).resolve()
            if not image_path.is_relative_to(self.root):
                raise ValueError(f"Image outside build output: {self.path}: {attrs['src']}")
            width, height = image_size(image_path)
            if not width or not height:
                raise ValueError(f"Image has zero dimensions: {image_path}")
            attrs.update(width=width, height=height, decoding="async")
            if self.images:
                attrs["loading"] = "lazy"
            else:
                attrs.pop("loading", None)
            self.images += 1
            self.replace_tag(tag, attrs)

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag == "thead":
            self.thead -= 1
        if tag == "head":
            self.head_end = self.position()

    def render(self, url=None):
        if url:
            if self.head_end is None:
                raise ValueError(f"Missing </head>: {self.path}")
            additions = []
            # A moved page may explicitly canonicalize to its replacement.
            url = self.canonical or url
            if not self.canonical:
                additions.append(f'<link rel="canonical" href="{escape(url, quote=True)}">\n')
            if not self.og_url:
                additions.append(f'<meta property="og:url" content="{escape(url, quote=True)}">\n')
            self.edits.append((self.head_end, self.head_end, "".join(additions)))
        html = self.html
        for start, end, text in sorted(self.edits, reverse=True):
            html = html[:start] + text + html[end:]
        return html


def main():
    root = Path(sys.argv[1]).resolve()
    urls = {ORIGIN + path for path in SIBLING_PAGES}
    indexes = images = headers = 0
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root)
        if "download" in relative.parts:
            continue
        page = Page(path.read_text(encoding="utf-8"), path, root)
        url = None
        if path.name == "index.html":
            indexes += 1
            folder = relative.parent.as_posix()
            url = ORIGIN + "/" + (quote(folder) + "/" if folder != "." else "")
            if (not page.noindex and not {"poster-review", "examples"}.intersection(relative.parts)
                    and folder != "library/ai-safety-seminar-1"):
                urls.add(page.canonical or url)
        html = page.render(url)
        # Wrap block equations in a focusable container: the overflow scroller
        # (and, when it scrolls, the keyboard focus target) must be a div,
        # because role="region" is not allowed on <math> (aria-allowed-role).
        if '<math display="block"' in html:
            html = re.sub(r'(<math display="block".*?</math>)',
                         r'<div class="mathwrap">\1</div>', html, flags=re.S)
        path.write_text(html, encoding="utf-8")
        images += page.images
        headers += page.headers

    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", namespace)
    sitemap = ET.Element(f"{{{namespace}}}urlset")
    for url in sorted(urls):
        entry = ET.SubElement(sitemap, f"{{{namespace}}}url")
        ET.SubElement(entry, f"{{{namespace}}}loc").text = url
    ET.indent(sitemap)
    ET.ElementTree(sitemap).write(root / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    print(f"post-build: {indexes} index pages, {images} images, {headers} column headers; sitemap: {len(urls)} URLs")


if __name__ == "__main__":
    main()
