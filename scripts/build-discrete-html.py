#!/usr/bin/env python3
"""Export the authored Discrete Mathematics chapters to Quarto reading pages.

Run after editing a chapter's LaTeX: python3 scripts/build-discrete-html.py
The LaTeX remains authoritative. Only selected chapter text and illustrations
are exported; the private course directory is never a Quarto resource.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "kitchen/courses/discrete-structures/lec_notes"
BUILD = ROOT / "kitchen/courses/discrete-structures/website-assets/html-notes"
PAGES = ROOT / "teaching/notes"
PREAMBLE = r"""\documentclass{book}
\newcommand{\N}{\mathbb{N}}
\newcommand{\Z}{\mathbb{Z}}
\newcommand{\R}{\mathbb{R}}
\newcommand{\True}{\text{\texttt{T}}}
\newcommand{\False}{\text{\texttt{F}}}
\begin{document}
"""


def group(s: str, pos: int, opening: str = "{") -> tuple[str, int]:
    while pos < len(s) and s[pos].isspace():
        pos += 1
    closing = "}" if opening == "{" else "]"
    if pos >= len(s) or s[pos] != opening:
        raise ValueError(f"Expected {opening} near {s[pos:pos + 100]!r}")
    start = pos + 1
    depth, braces = 1, 0
    pos += 1
    while pos < len(s):
        if s[pos] == "\\":
            pos += 2
            continue
        c = s[pos]
        if opening == "[":
            if c == "{": braces += 1
            elif c == "}": braces -= 1
        if not braces:
            if c == opening: depth += 1
            elif c == closing:
                depth -= 1
                if not depth: return s[start:pos], pos + 1
        pos += 1
    raise ValueError("Unclosed LaTeX argument")


def option(s: str, pos: int) -> tuple[str, int]:
    k = pos
    while k < len(s) and s[k].isspace(): k += 1
    return group(s, k, "[") if k < len(s) and s[k] == "[" else ("", pos)


def strip_comments(s: str) -> str:
    chunks = re.split(r"(\\begin\{verbatim\}.*?\\end\{verbatim\})", s, flags=re.S)
    for i in range(0, len(chunks), 2):
        chunks[i] = re.sub(r"(?<!\\)%[^\n]*", "", chunks[i])
    return "".join(chunks)


class Chapter:
    def __init__(self, number: int, assets: dict):
        self.number = number
        self.assets = assets
        self.labels: dict[str, str] = {}
        self.section = self.example = self.definition = 0
        self.current_ref = str(number)
        self.enums: list[dict] = []
        self.in_exercises = False
        self.exercise_count = 0
        self.title = "Introduction"

    def prepare(self, original: str) -> str:
        s = original.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
        s = strip_comments(s)
        s = re.sub(r"\\begin\{titlepage\}.*?\\end\{titlepage\}", "", s, flags=re.S)
        for diagram in self.assets["tikz"]:
            match = re.search(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", s, re.S)
            if not match or hashlib.sha256(match.group().encode()).hexdigest() != diagram["sha256"]:
                # The asset exporter hashes the original block, including comments.
                raw_blocks = re.findall(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", original, re.S)[1:]
                assert hashlib.sha256(raw_blocks[diagram["index"] - 1].encode()).hexdigest() == diagram["sha256"]
            assert match
            s = s[:match.start()] + r"\includegraphics{" + diagram["url"] + "}" + s[match.end():]
        out: list[str] = []
        i = 0
        remove_args = {"Needspace": 1, "setlength": 2, "hypersetup": 1,
                       "thispagestyle": 1, "markboth": 2, "setChapColor": 2,
                       "vspace": 1, "pdfbookmark": 2, "setcounter": 2}
        unwrap = {"center", "minipage", "samepage", "twocolparts"}
        while i < len(s):
            if s[i] != "\\":
                out.append(s[i]); i += 1; continue
            m = re.match(r"\\([A-Za-z]+)(\*)?", s[i:])
            if not m:
                out.append(s[i:i+2]); i += 2; continue
            name, star = m.group(1), m.group(2) or ""
            end = i + len(m.group())
            if name in remove_args:
                _, end = option(s, end)
                for _ in range(remove_args[name]): _, end = group(s, end)
                i = end; continue
            if name in {"posttablespace", "hfill", "null"}:
                i = end; continue
            if name == "nopagebreak":
                _, i = option(s, end); continue
            if name == "input":
                value, i = group(s, end)
                assert value == "chapter_00_cover", value
                continue
            if name == "chapter":
                short, end = option(s, end); value, i = group(s, end)
                self.title = (short or value).replace(r"\\", " ")
                continue
            if name == "section":
                value, i = group(s, end)
                if not star:
                    self.section += 1; self.current_ref = f"{self.number}.{self.section}"
                    self.in_exercises = value == "Exercises"
                    value = self.current_ref + " " + value
                out.append(r"\section" + star + "{" + value + "}")
                continue
            if name == "refstepcounter":
                counter, i = group(s, end); assert counter == "workedexample"
                self.example += 1; self.current_ref = f"{self.number}.{self.example}"
                continue
            if name == "theworkedexample":
                out.append(f"{self.number}.{self.example}"); i = end; continue
            if name == "thechapter":
                out.append(str(self.number)); i = end; continue
            if name == "label":
                label, i = group(s, end)
                if label in self.labels: raise ValueError(f"Duplicate label {label}")
                self.labels[label] = self.current_ref
                out.append(r"\label{" + label + "}"); continue
            if name == "includegraphics":
                _, end = option(s, end); path, i = group(s, end)
                raster = next((x for x in self.assets["rasters"] if x["source"] == path), None)
                assert raster or path.startswith("/teaching/notes/assets/"), path
                out.append(r"\includegraphics{" + (raster["url"] if raster else path) + "}")
                continue
            if name == "qed":
                out.append(r"\(\square\)"); i = end; continue
            if name in {"begin", "end"}:
                env, end = group(s, end)
                if env == "verbatim" and name == "begin":
                    last = s.index(r"\end{verbatim}", end) + len(r"\end{verbatim}")
                    out.append(s[i:last]); i = last; continue
                if env in unwrap:
                    if env == "minipage" and name == "begin":
                        _, end = option(s, end); _, end = group(s, end)
                    out.append("\n"); i = end; continue
                if env == "enumerate":
                    if name == "begin":
                        opts, end = option(s, end)
                        alpha = r"\alph" in opts
                        start = re.search(r"start\s*=\s*(\d+)", opts)
                        value = int(start.group(1)) if start else 1
                        self.enums.append({"count": value-1, "alpha": alpha,
                                           "exercises": self.in_exercises and not self.enums})
                        out.append(r"\begin{enumerate}" + ("[a)]" if alpha else "[1.]"))
                        if value != 1:
                            counter = ["enumi", "enumii", "enumiii", "enumiv"][len(self.enums)-1]
                            out.append(r"\setcounter{" + counter + "}{" + str(value-1) + "}")
                    else:
                        self.enums.pop(); out.append(r"\end{enumerate}")
                    i = end; continue
                if env in {"definition", "learningoutcomes", "studybox", "caution", "pythonexample", "tcolorbox"}:
                    if name == "end":
                        out.append(r"\end{" + env + "}"); i = end; continue
                    opts, end = option(s, end)
                    label = re.search(r"(?:^|,)\s*label\s*=\s*([^,}\s]+)", opts)
                    if env in {"definition", "studybox", "caution"}: title, end = group(s, end)
                    elif env == "learningoutcomes": title = "What you should be able to do"
                    elif env == "pythonexample": title = "Python (non-examinable)"
                    else:
                        tm = re.search(r"(?:^|,)\s*title\s*=\s*", opts)
                        if not tm: raise ValueError("Untitled tcolorbox")
                        title, _ = group(opts, tm.end())
                    if env == "definition":
                        self.definition += 1; self.current_ref = f"{self.number}.{self.definition}"
                        title = f"Definition {self.current_ref}: " + title
                    out.append(r"\begin{" + env + r"}\paragraph{" + title + "}")
                    if label:
                        self.labels[label.group(1)] = self.current_ref
                        out.append(r"\label{" + label.group(1) + "}")
                    i = end; continue
                out.append(s[i:end]); i = end; continue
            if name == "item" and self.enums:
                current = self.enums[-1]; current["count"] += 1
                if current["exercises"]:
                    self.exercise_count += 1
                    self.current_ref = f"{self.number}.{current['count']}"
                elif current["alpha"]:
                    self.current_ref = chr(96 + current["count"])
            out.append(m.group()); i = end
        prepared = "".join(out)
        def reference(match):
            key = match.group(1)
            if key not in self.labels: raise ValueError(f"Unknown reference {key}")
            return r"\hyperlink{" + key + "}{" + self.labels[key] + "}"
        prepared = re.sub(r"\\ref\{([^}]+)\}", reference, prepared)
        return PREAMBLE + prepared + "\n\\end{document}\n"


def text_value(x) -> str:
    if isinstance(x, list): return "".join(text_value(t) for t in x)
    if not isinstance(x, dict): return ""
    if x["t"] in {"Str", "Code", "Math"}:
        return x["c"] if isinstance(x["c"], str) else x["c"][-1]
    if x["t"] in {"Space", "SoftBreak", "LineBreak"}: return " "
    return text_value(x.get("c", []))


def para(content): return {"t": "Para", "c": content}
def div(content, classes, ident="", attrs=None):
    return {"t": "Div", "c": [[ident, classes, attrs or []], content]}


def adapt(node, chapter: Chapter):
    if isinstance(node, list):
        result = []; i = 0
        while i < len(node):
            item = node[i]
            if isinstance(item, dict) and item.get("t") == "Header" and item["c"][0] == 4:
                _, attr, words = item["c"]
                title = {"t": "Span", "c": [attr, [{"t": "Strong", "c": words}]]}
                content = [title]
                if i+1 < len(node) and isinstance(node[i+1], dict) and node[i+1].get("t") == "Para":
                    content += [{"t": "Space"}] + node[i+1]["c"]; i += 1
                result.append(para(content))
            else: result.append(adapt(item, chapter))
            i += 1
        return result
    if not isinstance(node, dict): return node
    kind = node.get("t")
    if kind == "Div":
        attr, blocks = node["c"]
        styles = {"definition": "definition", "learningoutcomes": "learningoutcomes",
                  "studybox": "studybox", "caution": "caution", "pythonexample": "python", "tcolorbox": "enrichment"}
        box = next((x for x in attr[1] if x in styles), None)
        if box:
            assert blocks and blocks[0]["t"] == "Header", box
            _, heading_attr, words = blocks[0]["c"]
            title = div([para([{"t": "Strong", "c": words}])], ["ds-box-title"], heading_attr[0])
            body = adapt(blocks[1:], chapter)
            if box == "pythonexample":
                codes = [x for x in descendants(body) if x.get("t") == "CodeBlock"]
                assert len(codes) == 2
                codes[0]["c"][0][1] = ["python"]
                codes[1]["c"][0][1] = ["text"]
            return div([title] + body, ["ds-box", "ds-" + styles[box]], attr[0])
    if kind == "Header":
        node["c"][0] += 1
    if kind == "Image":
        attr, _, target = node["c"]
        asset = next(x for x in chapter.assets["rasters"] + chapter.assets["tikz"] if x["url"] == target[0])
        node["c"] = [[attr[0], ["ds-note-image"], [["fig-alt", asset["alt"]], ["loading", "lazy"], ["decoding", "async"]]], [], target]
        return node
    if kind == "Table":
        node["c"] = adapt(node["c"], chapter)
        return div([node], ["ds-table"])
    return {key: adapt(value, chapter) for key, value in node.items()}


def descendants(node):
    if isinstance(node, dict):
        if "t" in node: yield node
        for value in node.values(): yield from descendants(value)
    elif isinstance(node, list):
        for value in node: yield from descendants(value)


def pandoc(arguments, content):
    result = subprocess.run(["quarto", "pandoc", *arguments], input=content, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=SOURCES, check=True)
    if result.stderr.strip(): raise ValueError(result.stderr)
    return result.stdout


def make_page(number, assets):
    source = SOURCES / f"chapter_{number:02}.tex"
    original = source.read_text()
    chapter = Chapter(number, assets[str(number)])
    prepared = chapter.prepare(original)
    assert original.count(r"\underline{\hspace{") == prepared.count(r"\underline{\hspace{")
    assert chapter.example == original.count(r"\refstepcounter{workedexample}")
    assert chapter.definition == original.count(r"\begin{definition}")
    doc = json.loads(pandoc(["--from=latex", "--to=json"], prepared))
    doc["blocks"] = adapt(doc["blocks"], chapter)
    for i, block in enumerate(doc["blocks"]):
        if block["t"] == "Header" and text_value(block["c"][2]).endswith(" Exercises"):
            following = doc["blocks"][i+1:]
            assert len(following) == 1 and following[0]["t"] == "OrderedList"
            assert len(following[0]["c"][1]) == chapter.exercise_count
            doc["blocks"][i+1:] = [div(following, ["ds-exercises"], attrs=[["style", f"--ds-chapter: '{number}';"]])]
            break
    nodes = list(descendants(doc["blocks"]))
    ids = []
    for x in nodes:
        if x["t"] == "Header": ids.append(x["c"][1][0])
        elif x["t"] in {"Div", "Span", "CodeBlock", "Link", "Image"}: ids.append(x["c"][0][0])
    ids = [x for x in ids if x]
    assert len(ids) == len(set(ids)), f"Duplicate HTML anchors: chapter {number}"
    for label in chapter.labels: assert label in ids, f"Lost source label {label}"
    for x in nodes:
        assert x["t"] not in {"RawBlock", "RawInline"}, x
        if x["t"] == "Link" and x["c"][2][0].startswith("#"):
            assert x["c"][2][0][1:] in ids, x
        if x["t"] == "Math":
            assert not re.search(r"\\(?:N|Z|R|True|False|thechapter|theworkedexample)\b", x["c"][1]), x
    counts = Counter(x["t"] for x in nodes)
    assert counts["Table"] == len(re.findall(r"\\begin\{(?:tabular|tabularx)\}", original))
    assert counts["Image"] == len(chapter.assets["rasters"]) + len(chapter.assets["tikz"])
    literal = re.findall(r"\\begin\{verbatim\}\n?(.*?)\\end\{verbatim\}", original, re.S)
    assert [x["c"][1] for x in nodes if x["t"] == "CodeBlock"] == [x.rstrip("\n") for x in literal]
    boxes = [x for x in nodes if x["t"] == "Div" and "ds-python" in x["c"][0][1]]
    assert len(boxes) == original.count(r"\begin{pythonexample}")
    title = "Introduction" if number == 0 else f"Chapter {number}: {chapter.title}"
    route = f"/teaching/notes/chapter-{number:02}/"
    pdf = f"/teaching/bulsu/discrete-math/lecture-notes/chapter_{number:02}.pdf"
    metadata = {
        "title": title, "subtitle": "Discrete Mathematics · Rey Joseph Nieto",
        "description": f"{title}. HTML edition of Lecture Notes in Discrete Mathematics.",
        "canonical-url": "https://rjnieto.com" + route,
        "header-includes": '<meta name="robots" content="index, follow, max-image-preview:large">\n'
                           + f'<meta property="og:url" content="https://rjnieto.com{route}">\n'
                           + '<meta property="og:type" content="article">',
        "image": f"/teaching/bulsu/discrete-math/images/thumbnails/chapter_{number:02}.webp",
        "body-classes": "ds-lecture-notes", "toc": True, "toc-depth": 2,
        "number-sections": False,
        "format": {"html": {"css": ["/assets/css/discrete-notes.css"]}},
        "execute": {"eval": False},
    }
    # JSON is valid YAML and safely quotes mathematical titles and punctuation.
    front = "---\n" + json.dumps(metadata, indent=2, ensure_ascii=False) + "\n---\n\n"
    buttons = f"[Course page](/teaching/){{.btn .btn-outline-secondary .btn-sm}} [PDF]({pdf}){{.btn .btn-outline-primary .btn-sm aria-label=\"Open {title} as PDF\"}}\n\n"
    content = pandoc(["--from=json", "--to=markdown", "--wrap=none"], json.dumps(doc))
    nav = []
    if number > 0: nav.append(f"[← {'Introduction' if number == 1 else 'Chapter ' + str(number-1)}](../chapter-{number-1:02}/index.qmd)")
    if number < 12: nav.append(f"[Chapter {number+1} →](../chapter-{number+1:02}/index.qmd)")
    page = front + "<!-- Generated from the corresponding chapter LaTeX. Run scripts/build-discrete-html.py to refresh. -->\n\n" + buttons + content
    page += "\n::: {.ds-chapter-navigation}\n\n" + " · ".join(nav) + "\n\n:::\n"
    (BUILD / f"chapter_{number:02}.prepared.tex").write_text(prepared)
    (BUILD / f"chapter_{number:02}.ast.json").write_text(json.dumps(doc, ensure_ascii=False))
    metrics = {"chapter": number, "title": title, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "labels": chapter.labels, "worked_examples": chapter.example, "definitions": chapter.definition,
               "exercises": chapter.exercise_count, "tables": counts["Table"], "images": counts["Image"],
               "python_boxes": len(boxes), "code_blocks": counts["CodeBlock"], "math_expressions": counts["Math"]}
    return page, metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check generated pages without rewriting them")
    parser.add_argument("--skip-assets", action="store_true", help="Reuse the already-verified asset export")
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    if not args.skip_assets:
        subprocess.run(["python3", str(ROOT / "scripts/discrete_html_assets.py")], check=True, cwd=ROOT)
    assets = json.loads((BUILD / "assets.json").read_text())
    metrics = []
    for number in range(13):
        page, report = make_page(number, assets)
        destination = PAGES / f"chapter-{number:02}" / "index.qmd"
        if args.check:
            assert destination.is_file() and destination.read_text() == page, f"Stale HTML source: {destination}"
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(page)
        metrics.append(report)
        print(f"Chapter {number:02}: {report['worked_examples']} examples, {report['exercises']} exercises, {report['images']} figures")
    (BUILD / "conversion_manifest.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
