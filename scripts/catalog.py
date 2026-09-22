"""Load and validate the shared source of truth for the gallery and post drafts."""

from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
REQUIRED_FIELDS = {"id", "title", "author", "desc"}
OPTIONAL_FIELDS = {"site", "contact"}


class CatalogLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if any(not isinstance(key, str) for key in keys):
            raise ValueError(
                f"YAML field names must be text on line {node.start_mark.line + 1}"
            )
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate YAML field on line {node.start_mark.line + 1}")
        return super().construct_mapping(node, deep=deep)


def validate_url(value, field, entry_id):
    url = urlsplit(value)
    if url.scheme in {"http", "https"} and url.hostname:
        return
    if field == "contact" and url.scheme == "mailto" and "@" in url.path:
        return
    raise ValueError(
        f"Entry #{entry_id}: {field} must be an HTTP(S) URL"
        + (" or mailto link" if field == "contact" else "")
    )


def load_entries(root=ROOT_DIR):
    entries = yaml.load(
        (root / "examples.yml").read_text(encoding="utf-8"), Loader=CatalogLoader
    )
    if not isinstance(entries, list) or not entries:
        raise ValueError("examples.yml must contain a nonempty list of entries")

    previous_id = None
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry {position} must be a mapping")
        missing = REQUIRED_FIELDS - entry.keys()
        unknown = entry.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS
        if missing or unknown:
            raise ValueError(
                f"Entry {position}: missing fields {sorted(missing)}; "
                f"unknown fields {sorted(unknown)}"
            )

        entry_id = entry["id"]
        if type(entry_id) is not int or entry_id < 1:
            raise ValueError(f"Entry {position}: id must be a positive integer")
        if previous_id is not None and entry_id >= previous_id:
            raise ValueError(f"Entry #{entry_id}: IDs must be unique and descending")
        previous_id = entry_id

        for field, value in entry.items():
            if field == "id":
                continue
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or any(ord(char) < 32 for char in value)
            ):
                raise ValueError(
                    f"Entry #{entry_id}: {field} must be nonempty, "
                    "single-line text without surrounding whitespace"
                )
            if field in OPTIONAL_FIELDS:
                if any(char.isspace() for char in value):
                    raise ValueError(f"Entry #{entry_id}: {field} contains whitespace")
                validate_url(value, field, entry_id)

    return entries


def validate_previews(entries, root=ROOT_DIR):
    for entry in entries:
        entry_id = entry["id"]
        image_path = root / "images" / f"{entry_id}.gif"
        if not image_path.is_file():
            raise ValueError(
                f"Entry #{entry_id}: missing {image_path.relative_to(root)}"
            )
        with image_path.open("rb") as image:
            if image.read(6) not in {b"GIF87a", b"GIF89a"}:
                raise ValueError(f"Entry #{entry_id}: preview must be a GIF image")
