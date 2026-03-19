# Pyxel User Examples

Works made with [Pyxel](https://github.com/kitao/pyxel), a retro game engine for Python.

## Site

Published via GitHub Pages: https://kitao.github.io/pyxel-user-examples/

## How to update

1. Edit `examples.yml` to add/remove entries
2. Add screenshot images to `images/` (named `{id}.gif`)
3. Run the generator:

```bash
.venv/bin/python generate.py
```

4. Commit and push

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install pyyaml
```

## Files

| File | Description |
|------|-------------|
| `examples.yml` | Source data for all entries |
| `page.html` | HTML template |
| `styles.css` | Stylesheet |
| `generate.py` | Builds `index.html` and `pages/*.html` from the template and data |
| `index.html` | Generated – latest entries page |
| `pages/` | Generated – older entries pages |
| `images/` | Screenshot GIFs |

## Submit your project

Please share yours [here](https://github.com/kitao/pyxel/issues/671)!
