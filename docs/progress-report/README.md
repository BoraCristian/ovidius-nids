# Progress report — LaTeX sources

This folder holds the LaTeX sources for the bachelor's thesis
**progress report** for *Ovidius NIDS — Signature-based and Machine-Learning-based
Network Intrusion Detection with built-in Forensics*.

It is **not** the final thesis: it is a snapshot of the current state,
intended for presentation to the coordinating teacher.

## Folder layout

```
docs/progress-report/
├── main.tex                ← root document (preamble + \input commands)
├── references.bib          ← BibLaTeX bibliography
├── sections/
│   ├── title.tex
│   ├── abstract.tex
│   ├── introduction.tex
│   ├── background.tex
│   ├── related_work.tex
│   ├── architecture.tex
│   ├── implementation.tex
│   ├── current_state.tex
│   └── future_work.tex
└── README.md               ← this file
```

## How to build the PDF

You need a TeX distribution (TeX Live, MiKTeX, or MacTeX) with the
`biber` backend. From inside this folder:

```
latexmk -pdf main.tex
```

If `latexmk` is not available, the manual sequence is:

```
pdflatex main.tex
biber main
pdflatex main.tex
pdflatex main.tex
```

The output PDF will be `main.pdf`.

## Editing tips

- The title page expects the coordinator's name in
  `sections/title.tex` — replace `[Numele coordonatorului]` before
  printing.
- All section content lives under `sections/`. Each `\input{...}` in
  `main.tex` corresponds to one file. To add a section, create a new
  `.tex` file under `sections/` and `\input` it from `main.tex`.
- References are managed by **BibLaTeX + biber**. To add a citation,
  put the BibTeX entry into `references.bib` and cite it with
  `\cite{key}` in the text.

## Translating to Romanian

The report is currently in English (the project title is also in
English). If the defense requires a Romanian version:

1. Replace `\usepackage[english]{babel}` with
   `\usepackage[romanian]{babel}` in `main.tex`.
2. Translate the contents of each file under `sections/`.

## Online editing

You can drop the entire `docs/progress-report/` folder into Overleaf as
a new project and it will build out of the box (Overleaf's compiler
defaults to `latexmk` and supports biber).
