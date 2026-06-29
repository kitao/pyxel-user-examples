# Pyxel User Examples

https://kitao.github.io/pyxel-user-examples/

Pyxel User Examples collects projects made with
[Pyxel](https://github.com/kitao/pyxel).

## Files

- `examples.yml`: Source data for the example list.
- `images/*.gif`: Preview images named by example ID.
- `page.html`: Template for the generated pages.
- `index.html` and `pages/*.html`: Generated pages.

## Maintenance

After editing `examples.yml`, `page.html`, or preview images, regenerate the
HTML pages:

```sh
python3 scripts/build_pages
```

To draft an X post for an entry ID:

```sh
python3 scripts/draft_post <id>
```
