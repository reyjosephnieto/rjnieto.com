#!/usr/bin/env python3
"""Export only the concept illustrations used by the Discrete Mathematics notes.

The private LaTeX chapters remain authoritative. PNG originals are copied as
metadata-free WebP derivatives; TikZ pictures are compiled without changing
their source and exported as SVG paths. Build records stay in kitchen/.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "kitchen/courses/discrete-structures/lec_notes"
PRIVATE = ROOT / "kitchen/courses/discrete-structures/website-assets/html-notes"
PUBLIC = ROOT / "teaching/notes/assets"
MANIFEST = PRIVATE / "assets.json"
SCHEMA = 1
RENDERER = "discrete-html-assets-1"

TIKZ_ALTS = {
    6: [
        "Drawing 1: a graph on vertices a to f with edges ab, ac, bc, bd, ce, de and ef.",
        "Drawing 2: the same labelled graph rearranged; a crossing of edges does not create a vertex.",
        "Spanning tree T1, with edges ab, ac, bd, ce and ef.",
        "Spanning tree T2, with edges ab, bc, bd, de and ef.",
        "A tree rooted at a: a has children b and c, and b has children d and e.",
        "The same tree rooted at c: a is below c, b is below a, and d and e are below b.",
    ],
    7: [
        "Directed relation on 1, 2 and 3: a loop at 1, arrows both ways between 1 and 2, and an arrow from 2 to 3.",
        "Composing relations: Alice reaches p and q, Bob reaches p, p reaches s, and q reaches s and t; Charlie has no first step.",
        "A partition with three disjoint blocks: {1, 3}, {2, 4}, and {5}.",
    ],
    8: [
        "Number line locating -13 two units after -15, so -13 equals 5 times -3 plus the remainder 2.",
    ],
    9: [
        "Choice tree for codes A0, A1, A2, B0, B1 and B2: two first-letter choices, each with three digit choices.",
        "Unequal branching: A leads to AA, AB and AC; B leads to BB and BC; C leads only to CC.",
        "Two-set Venn diagram: 12 in A only, 6 in both sets, 8 in B only, and 14 outside both.",
        "Three-set Venn diagram: A only 9, B only 8, C only 6; AB only 7, AC only 5, BC only 4; all three 5; outside 6.",
    ],
    10: [
        "Pascal's triangle for rows n equals 0 through 6, highlighting 6 and 4 in row 4 and their sum 10 in row 5.",
    ],
    11: [
        "Successive sequence terms a0 equals 5, a1 equals 8, a2 equals 11 and a3 equals 14, joined by increments of 3.",
        "Square arrays with side lengths 1, 2 and 3, representing s0 equals 1, s1 equals 4 and s2 equals 9.",
    ],
    12: [
        "The base tree: a single leaf, denoted by a bullet.",
        "Tree B equals Node of two leaves: one root with a left leaf and a right leaf.",
        "Tree A equals Node of a leaf and B: a left leaf and a right internal vertex with two leaf children.",
    ],
}

RASTER_ALTS = {
    "assets/neural-network.png": "A layered artificial neural network, with connections carrying information from input through hidden layers to output.",
    "01-default-printer-function.png": "Students assigned to default printers, illustrating one output for each input.",
    "02-quantifier-order-permissions.png": "User and folder permissions illustrating how changing the order of quantifiers changes a claim.",
    "01-implication-and-converse.png": "An implication and its converse compared using connections and cables.",
    "01-odd-plus-odd-pairing.png": "Two odd collections paired to illustrate why an odd number plus an odd number is even.",
    "01-set-operations-permissions.png": "Permission sets illustrating union, intersection and set difference.",
    "02-disjoint-inputs-shared-image.png": "Disjoint input sets whose images share an output.",
    "01-next-odd-border.png": "A square enlarged by an odd-numbered border, illustrating the inductive step for a sum of odd numbers.",
    "02-four-starting-chains.png": "Four starting cases extending along separate chains, illustrating an induction step of size four.",
    "01-leaf-deletion.png": "A leaf and its incident edge removed from a tree, leaving a smaller tree.",
    "01-printer-equivalence-classes.png": "Students grouped into equivalence classes according to their assigned default printer.",
    "01-modular-wraparound.png": "Modular arithmetic illustrated by positions wrapping around a cycle.",
    "01-subsets-as-bits.png": "Subsets represented by binary strings, with one inclusion choice for each element.",
    "01-orders-and-subsets.png": "Ordered arrangements compared with unordered subsets.",
    "01-same-recurrence-different-starts.png": "Sequences following the same recurrence from different initial values.",
    "01-inverse-image-matching-inputs.png": "An inverse image collecting every input whose output belongs to a chosen set.",
    "02-recursive-leaf-count.png": "The leaf count of a binary tree obtained by adding the leaf counts of its two subtrees.",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    return digest(path.read_bytes())


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def body_source(text: str) -> str:
    """Exclude the cover, including the Introduction's cover helper."""
    text = re.sub(r"\\begin\{titlepage\}.*?\\end\{titlepage\}", "", text, flags=re.S)
    text = re.sub(r"\\input\{chapter_00_cover(?:\.tex)?\}", "", text)
    return text.split(r"\begin{document}", 1)[-1].split(r"\end{document}", 1)[0]


def balanced_argument(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise ValueError("Expected a braced LaTeX argument")
    level = 1
    i = start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "{":
            level += 1
        elif text[i] == "}":
            level -= 1
            if not level:
                return text[start + 1:i], i + 1
        i += 1
    raise ValueError("Unclosed LaTeX argument")


def tikz_settings(text: str) -> str:
    preamble = text.split(r"\begin{document}", 1)[0]
    settings = []
    for match in re.finditer(r"\\tikzset\s*(?=\{)", preamble):
        argument, end = balanced_argument(preamble, match.end())
        settings.append(r"\tikzset{" + argument + "}")
    return "\n".join(settings)


def standalone_preamble(style: str, chapter: str) -> str:
    colours = re.findall(r"\\definecolor\{[^}]+\}\{[^}]+\}\{[^}]+\}", style)
    libraries = re.findall(r"\\usetikzlibrary\{[^}]+\}", style)
    return "\n".join([
        r"\documentclass[11pt,border=4pt]{standalone}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath,amssymb,mathtools,xcolor,tikz}",
        r"\usepackage{libertinus,libertinust1math}",
        r"\usepackage{microtype}",
        *colours,
        *libraries,
        r"\newcommand{\ChapColor}{Cap1Blue}",
        r"\newcommand{\ChapColorLight}{LightBlue}",
        r"\newcommand{\N}{\mathbb N}",
        r"\newcommand{\Z}{\mathbb Z}",
        r"\newcommand{\R}{\mathbb R}",
        r"\newcommand{\True}{\text{\texttt{T}}}",
        r"\newcommand{\False}{\text{\texttt{F}}}",
        tikz_settings(chapter),
        "",
    ])


def run(command: list[str], cwd: Path) -> str:
    environment = os.environ.copy()
    environment.update({"LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"})
    result = subprocess.run(command, cwd=cwd, env=environment, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed in {relative(cwd)}:\n{result.stdout[-8000:]}")
    return result.stdout


def sanitise_svg(source: str) -> str:
    source = re.sub(r"<!--.*?-->", "", source, flags=re.S)
    source = re.sub(r"<metadata\b[^>]*>.*?</metadata\s*>", "", source, flags=re.S)
    tree = ET.fromstring(source)
    for element in tree.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local in {"script", "foreignObject", "metadata", "text"}:
            raise ValueError(f"Unexpected public SVG element: {local}")
        for key, value in element.attrib.items():
            if key.rsplit("}", 1)[-1] == "href" and not value.startswith("#"):
                raise ValueError("Public SVG contains an external resource")
    if any(token in source for token in (str(ROOT), "/Users/", "file://", "kitchen/")):
        raise ValueError("Public SVG contains a private path")
    return source.strip() + "\n"


def export_raster(chapter: int, source: str, previous: dict, counts: dict) -> dict:
    allowed = source == "assets/neural-network.png" and chapter == 0
    allowed |= source.startswith(f"concept_images/chapter_{chapter:02}/")
    if not allowed or not source.endswith(".png"):
        raise ValueError(f"Unapproved non-cover illustration: {source}")
    original = (NOTES / source).resolve()
    if not original.is_relative_to(NOTES) or not original.is_file():
        raise ValueError(f"Illustration not found in notes: {source}")
    filename = original.stem + ".webp"
    output = PUBLIC / f"chapter-{chapter:02}" / filename
    source_hash = file_digest(original)
    build_key = digest(f"{RENDERER}:webp:1600:90:{source_hash}".encode())
    cached = previous.get("build_key") == build_key and output.is_file()
    cached = cached and previous.get("output_sha256") == file_digest(output)
    if not cached:
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(original) as image:
            image = ImageOps.exif_transpose(image)
            image.load()
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            # A fresh image deliberately omits EXIF, ICC, XMP and other metadata.
            clean = Image.frombytes(image.mode, image.size, image.tobytes())
            temporary = output.with_suffix(".webp.tmp")
            clean.save(temporary, format="WEBP", quality=90, method=6)
            temporary.replace(output)
        counts["rasters_built"] += 1
    else:
        counts["rasters_cached"] += 1
    with Image.open(output) as image:
        width, height = image.size
        if set(image.info) & {"exif", "icc_profile", "xmp", "comment"}:
            raise ValueError(f"WebP metadata was retained: {output.name}")
    alt = RASTER_ALTS.get(source, RASTER_ALTS.get(original.name))
    if alt is None:
        raise ValueError(f"Add a human alt description for {source}")
    return {"source": source, "url": "/" + relative(output),
            "sha256": source_hash, "output_sha256": file_digest(output),
            "build_key": build_key, "width": width, "height": height,
            "bytes": output.stat().st_size, "alt": alt}


def export_tikz(chapter: int, index: int, block: str, preamble: str,
                tools: dict, previous: dict, counts: dict) -> dict:
    block_hash = digest(block.encode())
    dependencies = digest((preamble + json.dumps(tools, sort_keys=True)).encode())
    build_key = digest(f"{RENDERER}:svg:{block_hash}:{dependencies}".encode())
    output = PUBLIC / f"chapter-{chapter:02}" / f"diagram-{index:02}.svg"
    cached = previous.get("build_key") == build_key and output.is_file()
    cached = cached and previous.get("output_sha256") == file_digest(output)
    if not cached:
        build = PRIVATE / "build" / f"chapter-{chapter:02}" / f"diagram-{index:02}"
        build.mkdir(parents=True, exist_ok=True)
        tex = preamble + "\n\\begin{document}\n" + block + "\n\\end{document}\n"
        (build / "diagram.tex").write_text(tex)
        run(["pdflatex", "-no-shell-escape", "-interaction=nonstopmode",
             "-halt-on-error", "diagram.tex"], build)
        backend = "dvisvgm --pdf --no-fonts"
        try:
            run(["dvisvgm", "--pdf", "--no-fonts", "--precision=6",
                 "--output=diagram.svg", "diagram.pdf"], build)
        except RuntimeError as error:
            # Some MacTeX distributions omit the PDF backend's libgs/mutool.
            # Cairo also reads the exact standalone PDF and outlines its glyphs.
            if "can't retrieve number of pages" not in str(error) or "pdftocairo" not in tools:
                raise
            (build / "dvisvgm-diagnostic.txt").write_text(str(error) + "\n")
            run(["pdftocairo", "-svg", "diagram.pdf", "diagram.svg"], build)
            backend = "pdftocairo -svg (dvisvgm PDF backend unavailable)"
        cleaned = sanitise_svg((build / "diagram.svg").read_text())
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".svg.tmp")
        temporary.write_text(cleaned)
        temporary.replace(output)
        counts["tikz_built"] += 1
    else:
        # Validate cached output as well as its recorded digest.
        sanitise_svg(output.read_text())
        counts["tikz_cached"] += 1
        backend = previous.get("svg_backend", "dvisvgm --pdf --no-fonts")
    try:
        alt = TIKZ_ALTS[chapter][index - 1]
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Add a human alt description for chapter {chapter}, diagram {index}") from exc
    svg = ET.fromstring(output.read_text())
    return {"index": index, "sha256": block_hash,
            "url": "/" + relative(output), "alt": alt,
            "output_sha256": file_digest(output), "build_key": build_key,
            "dependencies_sha256": dependencies,
            "svg_backend": backend,
            "width": svg.get("width"), "height": svg.get("height"),
            "viewBox": svg.get("viewBox"), "bytes": output.stat().st_size}


def main() -> None:
    for name in ("pdflatex", "dvisvgm"):
        if shutil.which(name) is None:
            raise RuntimeError(f"Required local tool not found: {name}")
    if not subprocess.run(["kpsewhich", "standalone.cls"], capture_output=True,
                          text=True, check=True).stdout.strip():
        raise RuntimeError("The local TeX installation needs standalone.cls")
    tools = {name: subprocess.run([name, "--version"], text=True, check=True,
                                  capture_output=True).stdout.splitlines()[0]
             for name in ("pdflatex", "dvisvgm")}
    if shutil.which("pdftocairo"):
        version = subprocess.run(["pdftocairo", "-v"], text=True, check=True,
                                 capture_output=True)
        tools["pdftocairo"] = (version.stdout + version.stderr).splitlines()[0]
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    style_path = NOTES / "discrete_notes.sty"
    style = style_path.read_text()
    sources = [NOTES / f"chapter_{n:02}.tex" for n in range(13)]
    texts = {n: path.read_text() for n, path in enumerate(sources)}
    tracked = sources + [style_path]
    for n, text in texts.items():
        for source in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body_source(text)):
            tracked.append(NOTES / source)
    before = {relative(path): file_digest(path) for path in tracked}
    manifest: dict = {}
    counts = {"rasters_built": 0, "rasters_cached": 0,
              "tikz_built": 0, "tikz_cached": 0}
    for n, text in texts.items():
        body = body_source(text)
        raster_sources = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body)
        pictures = re.findall(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", body, re.S)
        old = previous.get(str(n), {})
        old_rasters = {item["source"]: item for item in old.get("rasters", [])}
        old_tikz = {item["index"]: item for item in old.get("tikz", [])}
        preamble = standalone_preamble(style, text)
        manifest[str(n)] = {
            "rasters": [export_raster(n, source, old_rasters.get(source, {}), counts)
                        for source in raster_sources],
            "tikz": [export_tikz(n, i, block, preamble, tools, old_tikz.get(i, {}), counts)
                     for i, block in enumerate(pictures, 1)],
        }
        print(f"Chapter {n:02}: {len(raster_sources)} raster(s), {len(pictures)} TikZ diagram(s)", flush=True)
    after = {relative(path): file_digest(path) for path in tracked}
    if before != after:
        changed = [path for path in before if before[path] != after[path]]
        raise RuntimeError(f"Source changed during the build: {changed}")
    manifest["_meta"] = {"schema": SCHEMA, "renderer": RENDERER, "tools": tools,
                         "source_sha256": before, "source_immutability_verified": True,
                         "raster_count": sum(len(manifest[str(n)]["rasters"]) for n in range(13)),
                         "tikz_count": sum(len(manifest[str(n)]["tikz"]) for n in range(13))}
    PRIVATE.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(MANIFEST)
    print(json.dumps({"manifest": relative(MANIFEST), **counts}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Asset export failed: {error}", file=sys.stderr)
        sys.exit(1)
