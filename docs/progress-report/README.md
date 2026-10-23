# Progress report — LaTeX sources

LaTeX sources for the bachelor's thesis **progress report** for *Ovidius NIDS —
Signature-based and Machine-Learning-based Network Intrusion Detection with
built-in Forensics*.

It is **not** the final thesis: it is a snapshot of the project's state at the
progress review, presented to the scientific coordinator. The compiled report is
[`main.pdf`](main.pdf); the final thesis lives in [`../thesis`](../thesis).

## Folder layout

```
docs/progress-report/
├── main.tex                ← root document (preamble + \input commands)
├── references.bib          ← BibTeX bibliography (natbib, plainnat style)
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
├── main.pdf                ← compiled report
└── README.md               ← this file
```

## How to build the PDF

You need a TeX distribution (TeX Live, MiKTeX, or MacTeX). From inside this
folder:

```
latexmk -pdf main.tex
```

If `latexmk` is not available, the manual sequence is:

```
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The folder also builds as-is on Overleaf.
