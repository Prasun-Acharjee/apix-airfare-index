# SIH 2026 idea presentation

The Smart India Hackathon 2026 idea submission for APIx, filled in from this
repository. Six slides, the SIH template layout, generated from a script so a
content change is a one-line edit and a rebuild rather than a manual redo.

| File | What it is |
|---|---|
| `SIH2026_APIx_Idea_Presentation.pptx` | the deck |
| `SIH2026_APIx_Idea_Presentation.pdf` | the same deck exported — **the portal accepts PDF only** |
| `build_deck.js` | the generator; all slide copy lives here |
| `assets/` | the SIH mark and the brain graphic, lifted from the official template |

## Before you upload

Four fields on slide 1 read `<fill from SIH portal>` and one team-name oval
reads `<Team Name>`. They are registration facts, not project facts, so they are
left blank on purpose:

- **Problem Statement ID** and **Theme** — from the problem statement you picked
- **Team ID** and **Team Name** — exactly as registered on the portal
- the **Team Name** oval at the top-left of slides 2–6 (`const TEAM` in the generator)

Check the **Problem Statement Title** against the portal wording too — the one on
the slide is descriptive, taken from `METHODOLOGY.md`, not copied from the
statement.

## Rebuilding

```bash
npm install pptxgenjs
node build_deck.js
soffice --headless --convert-to pdf SIH2026_APIx_Idea_Presentation.pptx
```

Slide copy is drawn from `README.md`, `METHODOLOGY.md` and `config/sources.yaml`.
If a number in this repo changes — the basket size, the test count, the number of
sources the robots audit permits — change it in `build_deck.js` too. The figures
currently on the slides are 975 basket cells, 74 tests, 3 of 9 sources permitted,
and a 0.05% endpoint error against synthetic ground truth.

## What is on each slide

1. **Title page** — the template fields, plus what the nightly run actually does
2. **Idea title** — the proposed solution, how it addresses the problem, what is novel
3. **Technical approach** — the stack, the ten-step pipeline, the index formula, the nightly job
4. **Feasibility and viability** — what already works, and four real risks against the code that answers each
5. **Impact and benefits** — who uses it, and the economic, social, governance and environmental case
6. **Research and references** — project artefacts, RFC 9309, the CPI manual, MoSPI and DGCA sources

The template's own instruction slide (a maximum of six slides, PDF only, do not
reword the section pointers) is followed: the deck is six slides and every
mandated pointer line is reproduced verbatim.
