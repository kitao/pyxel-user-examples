# Pyxel User Examples

A collection of games, tools, and other projects made with
[Pyxel](https://github.com/kitao/pyxel).

[Browse the gallery](https://kitao.dev/pyxel/user-examples/) or
[submit a project](https://github.com/kitao/pyxel/discussions/new?category=user-examples).

## Development

Use Python 3.10 or newer, Node.js 24 or newer, and Google Chrome. From the
repository root, set up the Python environment and install the dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
npm ci
npx playwright install webkit
```

Activate `.venv` in each new shell before running the commands below. On Linux,
use `npx playwright install --with-deps webkit` to install system dependencies too.

- `npm run dev`: preview the gallery at <http://localhost:4184/pyxel/user-examples/>.
- `npm run check`: run the script and browser tests, including all gallery previews.
- `npm run deploy:check`: run the checks and a deployment dry run without publishing.

Edit `examples.yml` and the matching `images/<id>.gif` to update a project.
The build replaces `dist/`; edit the sources, not the generated files.
