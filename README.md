# Pyxel User Examples

A collection of games, tools, and other projects made with
[Pyxel](https://github.com/kitao/pyxel).

[Browse the gallery](https://kitao.github.io/pyxel-user-examples/) or
[submit a project](https://github.com/kitao/pyxel/discussions/new?category=user-examples).

## Files

- `examples.yml`: Source data for the example list.
- `images/*.gif`: Preview images named by example ID.
- `templates/page.html`: Shared HTML template.
- `styles.css` and `lightbox.js`: Shared presentation and preview controls.
- `index.html` and `pages/*.html`: Generated pages.
- `scripts/`: Gallery builder, X post draft command, and shared data validation.
- `tests/`: Data validation and page generation regression tests.

## Maintenance

Use Python 3.9 or later. Install the build dependency in a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Add each new entry at the top of `examples.yml` with an ID one greater than the
current maximum, and save its preview as `images/<id>.gif`. Keep existing IDs
stable and entries in descending ID order.

| Field | Content |
| --- | --- |
| `id` | Unique positive integer |
| `title` | Project title, preserving the author's spelling |
| `author` | Author's display name |
| `desc` | Short description |
| `site` | Optional HTTP(S) link to the project |
| `contact` | Optional HTTP(S) author link or `mailto:` address |

Omit unavailable optional fields.

After editing the data, template, styles, preview script, or builder, regenerate
the HTML pages:

```sh
python3 scripts/build_pages
```

Check the data and generated files, then run the regression tests:

```sh
python3 scripts/build_pages --check
python3 -m unittest discover -s tests
```

Preview locally with `python3 -m http.server`, then open
<http://localhost:8000/>.

Commit source changes and regenerated pages together. GitHub Pages serves the
generated HTML; edit the source data or template to update it.

To draft an X post for an entry ID:

```sh
python3 scripts/draft_post <id>
```

This prints a draft without posting it.
