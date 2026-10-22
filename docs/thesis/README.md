# Bachelor's Thesis — LaTeX Sources

Full bachelor thesis: *Information System for Network Detection Intrusion*. Layout follows the
faculty's thesis template (Ovidius University, Faculty of Mathematics and
Computer Science, Computer Science degree): book class, two-sided, roman
front matter, double-line chapter headings, fancyhdr running headers.

**Output:** ~75 pages, English, 7 chapters + bibliography (31 references).
The submitted PDF is [`LICENTA_2026_Bora.RM.Cristian-Vasile.pdf`](LICENTA_2026_Bora.RM.Cristian-Vasile.pdf).

## Folder layout

```
docs/thesis/
├── main.tex                      ← root (preamble + \input commands)
├── references.bib                ← BibTeX bibliography
├── frontmatter/
│   ├── titlepage.tex             ← Ovidius-style title page
│   └── acknowledgements.tex
├── chapters/
│   ├── ch1-introduction.tex      ← Abstract, motivation, contributions
│   ├── ch2-background.tex        ← NIDS theory, signature vs ML, forensics
│   ├── ch3-technologies.tex      ← Per-technology sections (Python, FastAPI, ...)
│   ├── ch4-related-work.tex      ← Snort, Suricata, Zeek, Wazuh, Splunk
│   ├── ch5-design.tex            ← Architecture + implementation (largest)
│   ├── ch6-validation.tex        ← Synthetic attack validation + performance measurements
│   └── ch7-conclusions.tex       ← Achievements, limitations, future work
├── figures/                      ← university logo, architecture diagram, UI screenshots
└── README.md                     ← this file
```

## Build

Requires a TeX distribution (TeX Live, MiKTeX, or MacTeX).
From inside this folder:

```bash
latexmk -pdf main.tex
```

Or, without latexmk:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Output is `main.pdf`. The whole folder also builds as-is on Overleaf
(default compiler is latexmk).

## Editing tips

- Bibliography entries live in `references.bib`. Add a `@article{...}`
  or `@misc{...}` block, then cite it in any chapter with `\cite{key}`.

- The thesis uses `\file{...}` for source paths and `\code{...}` for
  inline code. Both macros are defined in `main.tex`.

- Code listings use the `lstlisting` environment with style `pyfile`
  (Python), `jsfile` (JavaScript), or `yamlfile`. See Chapter 5 for
  examples.

- To add a chapter, create `chapters/ch8-foo.tex` with
  `\chapter{Foo}\label{chap:foo}` at the top and add
  `\input{chapters/ch8-foo}` to `main.tex` after the existing chapters.
