# rjnieto.com

This repository contains the public Quarto source for
[rjnieto.com](https://rjnieto.com). The visible site presents mathematics,
research, teaching materials, and professional information.

## Repository boundaries

- Public Quarto pages live in `teaching/`, `mathematics/`, `cv/`, and the
  project root.
- Public static assets live in `assets/`; reusable HTML fragments live in
  `includes/`.
- Deliberate public downloads, such as teaching lecture notes, live beside the
  page that exposes them.
- `about.html`, `mmw/`, and `computational-topology/` preserve legacy URLs.
- `_site/` and `.quarto/` are generated and ignored.
- `source-material/` contains private working sources and references and is
  ignored in its entirety.

The Year 4 H1 section currently provides a single public overview of ongoing
independent study. Its working notes, LaTeX sources, and compiled PDFs remain
private under `source-material/`.

## Local preview

```sh
quarto preview --port 7969 --no-navigate
```

## Rendering and publication

```sh
quarto render
quarto publish gh-pages --no-prompt
```

Publishing is a separate, explicit action. Pushing the `main` branch does not
update the live website.
