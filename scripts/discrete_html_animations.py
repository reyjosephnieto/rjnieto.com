"""Apply explicit HTML-only figures after the LaTeX-derived AST is validated.

The source AST, chapter LaTeX, original illustrations and PDFs stay unchanged.
Placement guards deliberately fail when an authored anchor or caption moves.
"""
from __future__ import annotations

from copy import deepcopy
from html import escape
import json
from pathlib import Path, PurePosixPath
import posixpath
import re

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("discrete_animations.json")


def descendants(value):
    if isinstance(value, dict):
        if "t" in value:
            yield value
        for child in value.values():
            yield from descendants(child)
    elif isinstance(value, list):
        for child in value:
            yield from descendants(child)


def text(value):
    if isinstance(value, list):
        return "".join(text(child) for child in value)
    if not isinstance(value, dict):
        return ""
    kind = value.get("t")
    if kind in {"Space", "SoftBreak", "LineBreak"}:
        return " "
    if kind == "Str":
        return value["c"]
    if kind in {"Code", "Math"}:
        return value["c"][-1]
    return text(value.get("c", []))


def normal(value):
    return re.sub(r"\s+", " ", value).strip()


def validate_assets(entry, chapter):
    prefix = f"/teaching/notes/assets/chapter-{chapter:02}/"
    size = (entry["width"], entry["height"])
    if any(type(value) is not int or value <= 0 for value in size):
        raise ValueError(f"Invalid animation dimensions: {entry['id']}")
    for key, suffix in (("gif", ".gif"), ("poster", ".png")):
        url = entry[key]
        if (not url.startswith(prefix) or PurePosixPath(url).suffix != suffix
                or ".." in PurePosixPath(url).parts or any(c in url for c in "?#")):
            raise ValueError(f"Invalid animation resource: {url}")
        path = ROOT / url.lstrip("/")
        if not path.is_file():
            raise ValueError(f"Animation asset is not ready: {path.relative_to(ROOT)}")
        with Image.open(path) as image:
            if image.size != size:
                raise ValueError(f"Animation dimensions differ from the manifest: {url}")
            if key == "gif" and getattr(image, "n_frames", 1) < 2:
                raise ValueError(f"Animation GIF has only one frame: {url}")
            if key == "poster" and getattr(image, "n_frames", 1) != 1:
                raise ValueError(f"Animation poster must be static: {url}")


def caption_markup(inlines):
    parts = []
    for node in inlines:
        if node["t"] == "Str":
            parts.append(escape(node["c"]))
        elif node["t"] in {"Space", "SoftBreak", "LineBreak"}:
            parts.append(" ")
        elif node["t"] == "Math" and node["c"][0]["t"] == "InlineMath":
            # Quarto parses Markdown inside figcaption; preserve native TeX
            # until its HTML writer supplies MathJax delimiters and escaping.
            parts.append("$" + node["c"][1] + "$")
        elif node["t"] == "Code":
            parts.append("<code>" + escape(node["c"][1]) + "</code>")
        else:
            raise ValueError("Unsupported original animation caption markup")
    return "".join(parts)


def figure(entry, caption, *, html_caption=None):
    rendered_caption = escape(caption) if html_caption is None else html_caption
    html = (
        f'<figure id="{escape(entry["id"], quote=True)}" class="ds-animation">\n'
        '  <picture>\n'
        f'    <source media="print, (prefers-reduced-motion: reduce)" srcset="{escape(entry["poster"], quote=True)}">\n'
        f'    <img class="ds-note-image" src="{escape(entry["gif"], quote=True)}" '
        f'alt="{escape(entry["alt"], quote=True)}" width="{entry["width"]}" height="{entry["height"]}" '
        'loading="lazy" decoding="async">\n'
        '  </picture>\n'
        f'  <figcaption>{rendered_caption}</figcaption>\n'
        '</figure>'
    )
    return {"t": "RawBlock", "c": ["html", html]}


def apply_animations(document, chapter):
    """Return an HTML presentation AST, exact document resources and a report."""
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("schema") != 1:
        raise ValueError("Unsupported discrete animation manifest schema")
    entries = manifest.get("chapters", {}).get(str(chapter), [])
    if not entries:
        return document, [], []
    result = deepcopy(document)
    blocks = result["blocks"]
    identifiers = set()
    for node in descendants(result["blocks"]):
        if node["t"] == "Header":
            identifiers.add(node["c"][1][0])
        elif node["t"] in {"Div", "Span", "Image", "Link", "CodeBlock"}:
            identifiers.add(node["c"][0][0])
    resources, report = [], []
    for entry in entries:
        ident = entry["id"]
        if not re.fullmatch(r"[a-z][a-z0-9-]*", ident) or ident in identifiers:
            raise ValueError(f"Duplicate or invalid animation ID: {ident}")
        if not entry.get("alt", "").strip() or not (
                entry.get("caption", "").strip() or entry.get("existing_caption", "").strip()):
            raise ValueError(f"Animation needs alt text and a caption: {ident}")
        validate_assets(entry, chapter)
        identifiers.add(ident)
        if "after_paragraph_endswith" in entry and "replace_image" not in entry:
            suffix = entry["after_paragraph_endswith"]
            matches = [node for node in descendants(blocks) if node["t"] == "Para"
                       and normal(text(node["c"])).endswith(suffix)]
            if len(matches) != 1 or not any(node is matches[0] for node in blocks):
                raise ValueError(f"Animation paragraph anchor is not unique or moved: {ident}")
            index = next(i for i, node in enumerate(blocks) if node is matches[0])
            blocks.insert(index + 1, figure(entry, entry["caption"]))
            operation = "insert"
        elif "replace_image" in entry and "after_paragraph_endswith" not in entry:
            matches = [node for node in descendants(blocks) if node["t"] == "Image"
                       and node["c"][2][0] == entry["replace_image"]]
            paragraphs = [i for i, node in enumerate(blocks) if node["t"] == "Para"
                          and len(node["c"]) == 1 and node["c"][0] in matches]
            if len(matches) != 1 or len(paragraphs) != 1:
                raise ValueError(f"Animation image anchor is not unique or moved: {ident}")
            index = paragraphs[0]
            caption = blocks[index + 1] if index + 1 < len(blocks) else None
            expected = entry["existing_caption"]
            if (not caption or caption["t"] != "Para" or normal(text(caption["c"])) != expected
                    or any(node["t"] not in {"Str", "Space", "SoftBreak", "LineBreak", "Math", "Code"}
                           for node in caption["c"])):
                raise ValueError(f"Original animation caption changed or moved: {ident}")
            extra = entry.get("caption", "").strip()
            markup = caption_markup(caption["c"]) + (" " + escape(extra) if extra else "")
            blocks[index:index + 2] = [figure(entry, expected + (" " + extra if extra else ""), html_caption=markup)]
            operation = "replace"
        else:
            raise ValueError(f"Animation needs exactly one placement rule: {ident}")
        page_directory = f"teaching/notes/chapter-{chapter:02}"
        resources.extend(posixpath.relpath(entry[key].lstrip("/"), page_directory)
                         for key in ("gif", "poster"))
        if operation == "replace":
            # Retain previously published static-image URLs in clean builds.
            resources.append(posixpath.relpath(entry["replace_image"].lstrip("/"), page_directory))
        report.append({"id": ident, "operation": operation, "gif": entry["gif"], "poster": entry["poster"]})
    if len(resources) != len(set(resources)):
        raise ValueError("Animation resources must be unique")
    return result, resources, report
