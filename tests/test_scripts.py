"""Regression checks for catalog errors and safe, reproducible page generation."""

import runpy
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import load_entries  # noqa: E402 - Scripts are not an installed package.

BUILD = runpy.run_path(str(ROOT / "scripts" / "build_pages"))
DRAFT = runpy.run_path(str(ROOT / "scripts" / "draft_post"))


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.previews = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.urls.extend(attrs[key] for key in ("href", "src") if key in attrs)
        if tag == "img" and attrs.get("src"):
            self.previews.append(attrs["src"])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "images").mkdir()
        shutil.copytree(ROOT / "templates", self.root / "templates")
        for asset in ("styles.css", "lightbox.js"):
            shutil.copy(ROOT / asset, self.root / asset)
        self.entries = [
            {"id": 1, "title": "Example", "author": "Author", "desc": "A game"}
        ]
        self.write_catalog()

    def write_catalog(self):
        (self.root / "examples.yml").write_text(
            yaml.safe_dump(self.entries), encoding="utf-8"
        )
        for entry in self.entries:
            (self.root / "images" / f"{entry['id']}.gif").write_bytes(
                (ROOT / "images/1.gif").read_bytes()
            )

    def generate(self, check=False):
        with redirect_stdout(StringIO()):
            return BUILD["generate"](self.root, check=check)

    def test_rejects_bad_catalogs_without_changing_output(self):
        self.generate()
        original = (self.root / "index.html").read_bytes()
        cases = [
            [],
            None,
            "text",
            ["text"],
            [{"id": 1}],
            [dict(self.entries[0], id=True)],
            [dict(self.entries[0], id=-1)],
            [dict(self.entries[0], title=None)],
            [dict(self.entries[0], title=" title ")],
            [dict(self.entries[0], title="two\nlines")],
            [dict(self.entries[0], unexpected="field")],
            [dict(self.entries[0], site="javascript:alert(1)")],
            [dict(self.entries[0], site="https://")],
            [dict(self.entries[0], site="https://example.com/bad url")],
            [dict(self.entries[0], contact="invalid")],
            self.entries * 2,
            [self.entries[0], dict(self.entries[0], id=2)],
        ]
        for entries in cases:
            with self.subTest(entries=entries):
                (self.root / "examples.yml").write_text(
                    yaml.safe_dump(entries), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    self.generate()
                self.assertEqual((self.root / "index.html").read_bytes(), original)

    def test_rejects_duplicate_yaml_fields(self):
        (self.root / "examples.yml").write_text("- id: 1\n  id: 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate YAML field"):
            load_entries(self.root)

    def test_rejects_missing_or_wrong_image(self):
        image = self.root / "images/1.gif"
        image.unlink()
        with self.assertRaisesRegex(ValueError, "missing images/1.gif"):
            BUILD["render_pages"](self.root)
        image.write_text("not a GIF", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "GIF"):
            BUILD["render_pages"](self.root)

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
        self.assertTrue(output.getvalue().startswith("Example by Author is now on"))

    def test_pagination_boundaries(self):
        for count, pages in [(1, 1), (18, 1), (19, 2), (36, 2), (37, 3)]:
            with self.subTest(count=count):
                self.entries = [
                    dict(self.entries[0], id=i) for i in range(count, 0, -1)
                ]
                self.write_catalog()
                output = BUILD["render_pages"](self.root)
                self.assertEqual(len(output), pages)
                self.assertEqual(
                    sum(html.count('<div class="card">') for html in output.values()),
                    count,
                )

    def test_check_is_read_only_and_build_preserves_unrelated_files(self):
        self.assertEqual(self.generate(check=True), 1)
        self.assertFalse((self.root / "index.html").exists())
        pages = self.root / "pages"
        pages.mkdir()
        stale = pages / "18-1.html"
        stale.write_text("stale", encoding="utf-8")
        unrelated = pages / "custom.html"
        unrelated.write_text("keep me", encoding="utf-8")
        self.generate()
        self.assertFalse(stale.exists())
        self.assertEqual(unrelated.read_text(), "keep me")
        index = self.root / "index.html"
        modified = index.stat().st_mtime_ns
        self.assertEqual(self.generate(check=True), 0)
        self.generate()
        self.assertEqual(index.stat().st_mtime_ns, modified)
        index.write_text("outdated", encoding="utf-8")
        self.assertEqual(self.generate(check=True), 1)
        self.assertEqual(index.read_text(), "outdated")

    def test_text_and_links_are_escaped_once(self):
        self.entries[0].update(
            title='<b>"A&B"</b> $root {{nav}}',
            site="https://example.com/?a=1&b=2",
            contact="mailto:author@example.com",
        )
        self.write_catalog()
        html = BUILD["render_pages"](self.root)[self.root / "index.html"]
        self.assertIn("&lt;b&gt;&quot;A&amp;B&quot;&lt;/b&gt; $root {{nav}}", html)
        self.assertNotIn("<b>", html)
        self.assertIn('href="https://example.com/?a=1&amp;b=2"', html)

    def test_asset_changes_invalidate_generated_pages(self):
        self.generate()
        original = (self.root / "index.html").read_text(encoding="utf-8")
        with (self.root / "styles.css").open("a", encoding="utf-8") as css:
            css.write("\n/* Updated styles */\n")
        self.assertEqual(self.generate(check=True), 1)
        self.generate()
        self.assertNotEqual(
            (self.root / "index.html").read_text(encoding="utf-8"), original
        )
        self.assertEqual(self.generate(check=True), 0)

    def test_catalog_and_all_generated_local_links(self):
        entries = load_entries()
        output = BUILD["render_pages"]()
        previews = []
        for page, html in output.items():
            parser = PageParser()
            parser.feed(html)
            previews.extend(Path(url).name for url in parser.previews)
            for url in parser.urls:
                if not url:
                    continue
                if not urlsplit(url).scheme:
                    target = (page.parent / urlsplit(url).path).resolve()
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.is_file(), f"{page}: {url}")
        self.assertEqual(previews, [f"{entry['id']}.gif" for entry in entries])


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
        for entry_id, opening in [
            (214, "Moon Legend by mit-mit"),
            (209, "Pixel Flight Simulator by @0_game_it"),
        ]:
            with (
                self.subTest(entry_id=entry_id),
                patch.object(sys, "argv", ["draft_post", str(entry_id)]),
            ):
                output = StringIO()
                with redirect_stdout(output):
                    DRAFT["main"]()
                self.assertTrue(
                    output.getvalue().startswith(
                        opening + " is now on Pyxel User Examples!"
                    )
                )


if __name__ == "__main__":
    unittest.main()
