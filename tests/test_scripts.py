"""Regression checks for catalog errors and safe, reproducible gallery builds."""

import runpy
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import load_entries, read_preview_size

BUILD = runpy.run_path(str(ROOT / "scripts" / "build_pages"))
DRAFT = runpy.run_path(str(ROOT / "scripts" / "draft_post"))
SITE = BUILD["SITE_DIR"]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.links = []
        self.previews = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.urls.extend(attrs[key] for key in ("href", "src") if key in attrs)
        if tag == "link":
            self.links.append(attrs)
        if tag == "img":
            self.previews.append(attrs)


def make_source(root, entries):
    """Write a gallery source tree with the given entries into root."""
    shutil.copytree(ROOT / "templates", root / "templates")
    for name in ("_headers", *BUILD["ASSETS"]):
        shutil.copy(ROOT / name, root / name)
    (root / "images").mkdir()
    for entry in entries:
        shutil.copy(ROOT / "images/1.gif", root / f"images/{entry['id']}.gif")
    (root / "examples.yml").write_text(yaml.safe_dump(entries), encoding="utf-8")


def make_entries(count):
    return [
        {"id": i, "title": f"Example {i}", "author": "Author", "desc": "A game"}
        for i in range(count, 0, -1)
    ]


class BuildTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name).resolve()
        self.root = self.temp / "source"
        self.root.mkdir()
        self.entries = make_entries(1)
        make_source(self.root, self.entries)
        self.target = self.temp / "site"

    def write_catalog(self, entries):
        (self.root / "examples.yml").write_text(
            yaml.safe_dump(entries), encoding="utf-8"
        )

    def build(self):
        """Build the site and return its pages by their path in the gallery."""
        BUILD["build"](self.target, self.root)
        return {
            path.relative_to(self.target / SITE).as_posix(): path.read_text(
                encoding="utf-8"
            )
            for path in (self.target / SITE).rglob("index.html")
        }

    def test_rejects_bad_catalogs_before_writing(self):
        entry = self.entries[0]
        text = "single-line text"
        cases = [
            ([], "nonempty list"),
            (None, "nonempty list"),
            ("text", "nonempty list"),
            (["text"], "must be a mapping"),
            ([{"id": 1}], r"missing fields \['author', 'desc', 'title'\]"),
            ([dict(entry, unexpected="field")], r"unknown fields \['unexpected'\]"),
            ([dict(entry, id=True)], "positive integer"),
            ([dict(entry, id=-1)], "positive integer"),
            ([entry, entry], "unique and descending"),
            ([entry, dict(entry, id=2)], "unique and descending"),
            ([dict(entry, title=None)], text),
            ([dict(entry, title=" title ")], text),
            ([dict(entry, title="two\nlines")], text),
            ([dict(entry, title="two\u2028lines")], text),
            ([dict(entry, title="two\u2029paragraphs")], text),
            ([dict(entry, desc="next\x85line")], text),
            ([dict(entry, author="delete\x7f")], text),
            ([dict(entry, desc="lone \ud800 surrogate")], text),
            ([dict(entry, site="javascript:alert(1)")], r"HTTP\(S\) URL$"),
            ([dict(entry, site="https://")], r"HTTP\(S\) URL$"),
            ([dict(entry, site="https://example.com/bad url")], "whitespace"),
            ([dict(entry, contact="invalid")], "or mailto link"),
            ([dict(entry, contact="mailto:author")], "or mailto link"),
        ]
        for entries, message in cases:
            with self.subTest(entries=entries):
                self.write_catalog(entries)
                with self.assertRaisesRegex(ValueError, message):
                    self.build()
                self.assertFalse(self.target.exists())

    def test_rejects_duplicate_or_non_text_yaml_fields(self):
        for catalog, message in [
            ("- id: 1\n  id: 2\n", "Duplicate YAML field"),
            ("- id: 1\n  2: two\n", "field names must be text"),
        ]:
            with self.subTest(catalog=catalog):
                (self.root / "examples.yml").write_text(catalog, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    load_entries(self.root)

    def test_reads_preview_sizes_and_rejects_bad_previews(self):
        image = self.root / "images/1.gif"
        self.assertEqual(read_preview_size(1, self.root), (320, 240))
        image.write_bytes(b"GIF89a\x10\x00\x20\x00")
        self.assertEqual(read_preview_size(1, self.root), (16, 32))
        for content, message in [
            (b"not a GIF", "must be a GIF"),
            (b"GIF89a\x10\x00", "must be a GIF"),
            (b"GIF89a\x00\x00\x20\x00", "no size"),
        ]:
            with self.subTest(content=content):
                image.write_bytes(content)
                with self.assertRaisesRegex(ValueError, message):
                    self.build()
                self.assertFalse(self.target.exists())
        image.unlink()
        with self.assertRaisesRegex(ValueError, "missing images/1.gif"):
            self.build()

    def test_draft_does_not_require_preview_files(self):
        (self.root / "images/1.gif").unlink()
        output = StringIO()
        with (
            patch.dict(
                DRAFT["main"].__globals__, load_entries=lambda: load_entries(self.root)
            ),
            patch.object(sys, "argv", ["draft_post", "1"]),
            redirect_stdout(output),
        ):
            DRAFT["main"]()
        self.assertTrue(output.getvalue().startswith("Example 1 by Author is now on"))

    def test_page_urls_stay_as_entries_are_added(self):
        for count, paths in [
            (1, ["index.html"]),
            (18, ["index.html"]),
            (19, ["index.html", "page/2/index.html"]),
            (37, ["index.html", "page/2/index.html", "page/3/index.html"]),
        ]:
            with self.subTest(count=count):
                entries = make_entries(count)
                make_source(self.temp / f"source-{count}", entries)
                self.root = self.temp / f"source-{count}"
                pages = self.build()
                self.assertEqual(sorted(pages), paths)
                self.assertEqual(
                    sum(html.count('<div class="card">') for html in pages.values()),
                    count,
                )
                self.assertIn(f"#{count} Example {count}<", pages["index.html"])

    def test_build_replaces_the_contents_of_the_target(self):
        self.target.mkdir()
        (self.target / "stale").mkdir()
        (self.target / "stale/page.html").write_text("stale", encoding="utf-8")
        outside = self.temp / "outside"
        outside.mkdir()
        (outside / "file").write_text("outside", encoding="utf-8")
        (self.target / "link").symlink_to(outside)
        inode = self.target.stat().st_ino
        self.build()
        # A running wrangler dev keeps serving from the same directory.
        self.assertEqual(self.target.stat().st_ino, inode)
        # A symlink inside is removed without emptying what it points to.
        self.assertEqual((outside / "file").read_text(), "outside")
        self.assertEqual(
            sorted(
                path.relative_to(self.target).as_posix()
                for path in self.target.rglob("*")
                if path.is_file()
            ),
            [
                "_headers",
                f"{SITE}/images/1.gif",
                f"{SITE}/index.html",
                f"{SITE}/lightbox.js",
                f"{SITE}/styles.css",
            ],
        )

    def test_build_refuses_symlinked_sources(self):
        outside = self.temp / "outside"
        outside.mkdir()
        for name in (
            "examples.yml",
            "templates/page.html",
            "templates",
            "_headers",
            "styles.css",
            "images/1.gif",
            "images",
        ):
            with self.subTest(name=name):
                source = self.root / name
                moved = outside / source.name
                source.rename(moved)
                source.symlink_to(moved)
                with self.assertRaisesRegex(ValueError, "symlinks"):
                    self.build()
                self.assertFalse(self.target.exists())
                source.unlink()
                moved.rename(source)

    def test_build_checks_every_source_before_writing(self):
        for name in (
            "examples.yml",
            "templates/page.html",
            "_headers",
            *BUILD["ASSETS"],
        ):
            with self.subTest(name=name):
                source = self.root / name
                content = source.read_bytes()
                source.unlink()
                with self.assertRaises(FileNotFoundError):
                    self.build()
                self.assertFalse(self.target.exists())
                source.write_bytes(content)

    def test_main_replaces_dist_and_keeps_it_after_a_failure(self):
        dist = self.root / "dist"
        outside = self.temp / "outside"
        outside.mkdir()
        (outside / "file").write_text("outside", encoding="utf-8")
        dist.symlink_to(outside)

        def run():
            output = StringIO()
            with (
                patch.dict(BUILD["main"].__globals__, ROOT_DIR=self.root),
                patch.object(sys, "argv", ["build_pages"]),
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                try:
                    BUILD["main"]()
                except SystemExit as error:
                    return error.code
            return 0

        self.assertEqual(run(), 0)
        self.assertFalse(dist.is_symlink())
        self.assertTrue((dist / SITE / "index.html").is_file())
        self.assertEqual((outside / "file").read_text(), "outside")
        self.write_catalog([])
        self.assertEqual(run(), 1)
        self.assertTrue((dist / SITE / "index.html").is_file())
        self.assertEqual(
            sorted(path.name for path in self.root.iterdir()),
            [
                "_headers",
                "dist",
                "examples.yml",
                "images",
                "lightbox.js",
                "styles.css",
                "templates",
            ],
        )

    def test_text_and_links_are_escaped_once(self):
        self.write_catalog(
            [
                dict(
                    self.entries[0],
                    title='<b>"A&B"</b> {{ root }} {% raw %}',
                    site="https://example.com/?a=1&b=2",
                    contact="mailto:author@example.com",
                )
            ]
        )
        html = self.build()["index.html"]
        self.assertIn("&lt;b&gt;&#34;A&amp;B&#34;&lt;/b&gt; {{ root }} {% raw %}", html)
        self.assertNotIn("<b>", html)
        self.assertIn('href="https://example.com/?a=1&amp;b=2"', html)

    def test_catalog_and_all_generated_local_links(self):
        entries = load_entries()
        self.root = ROOT
        pages = self.build()
        documents = [
            self.target / SITE / name
            for name in sorted(pages, key=lambda name: (len(name), name))
        ]
        previews = []
        for document in documents:
            parser = PageParser()
            parser.feed(document.read_text(encoding="utf-8"))
            previews.extend(parser.previews)
            for url in parser.urls:
                parts = urlsplit(url)
                if parts.scheme:
                    continue
                if parts.path.startswith("/"):
                    if not parts.path.startswith(f"/{SITE}/"):
                        # The Pyxel site around the gallery provides these.
                        self.assertIn(
                            parts.path,
                            {"/pyxel/", "/pyxel/assets/images/pyxel_icon_64x64.png"},
                        )
                        continue
                    target = self.target / parts.path[1:]
                else:
                    target = document.parent / parts.path
                if parts.path.endswith("/"):
                    target /= "index.html"
                self.assertTrue(target.resolve().is_relative_to(self.target), url)
                self.assertTrue(target.is_file(), f"{document}: {url}")
        self.assertEqual(
            [Path(preview["src"]).name for preview in previews],
            [f"{entry['id']}.gif" for entry in entries],
        )
        # lightbox.js sizes the enlarged preview from these attributes.
        self.assertEqual(
            [(int(preview["width"]), int(preview["height"])) for preview in previews],
            [read_preview_size(entry["id"]) for entry in entries],
        )
        # Every page loads the shared font from Google Fonts.
        fonts = [
            {"rel": "preconnect", "href": "https://fonts.googleapis.com"},
            {
                "rel": "preconnect",
                "href": "https://fonts.gstatic.com",
                "crossorigin": None,
            },
            {
                "rel": "stylesheet",
                "href": "https://fonts.googleapis.com/css2?"
                "family=Noto+Sans+JP:wght@300..700&display=swap",
            },
        ]
        for document in documents:
            parser = PageParser()
            parser.feed(document.read_text(encoding="utf-8"))
            for link in fonts:
                self.assertIn(link, parser.links, document)


class DraftTests(unittest.TestCase):
    def test_profile_urls_only(self):
        extract = DRAFT["extract_x_username"]
        for url in ("https://x.com/Author", "https://twitter.com/Author/?lang=en"):
            self.assertEqual(extract(url), "@Author")
        for url in (
            "https://x.com/intent/post",
            "https://x.com/home",
            "https://x.com/Author/status/123",
            "https://x.com.evil/Author",
            "https://x.com/not-a-user",
            "https://github.com/Author",
            "",
        ):
            self.assertIsNone(extract(url), url)

    def test_draft_uses_handle_or_author(self):
        for contact, author in [
            ("https://github.com/Author", "Display Name"),
            ("https://x.com/Author", "@Author"),
        ]:
            entry = {
                "id": 1,
                "title": "Example",
                "author": "Display Name",
                "desc": "A game",
                "contact": contact,
            }
            with (
                self.subTest(contact=contact),
                patch.dict(
                    DRAFT["main"].__globals__, load_entries=lambda entry=entry: [entry]
                ),
                patch.object(sys, "argv", ["draft_post", "1"]),
            ):
                output = StringIO()
                with redirect_stdout(output):
                    DRAFT["main"]()
                self.assertTrue(
                    output.getvalue().startswith(
                        f"Example by {author} is now on Pyxel User Examples!"
                    )
                )


if __name__ == "__main__":
    unittest.main()
