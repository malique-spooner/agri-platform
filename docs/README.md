# Documentation guide

This directory separates the project's original brief, academic rationale, engineering references, and implementation evidence. The distinction matters because Agri-Platform Version 0 was intentionally scoped as an aggregator-facing university prototype rather than presented as the complete multi-channel product described in the original stakeholder dossier.

## Recommended reading order

1. [`source-material/original-dossier/`](source-material/original-dossier/) - the original stakeholder brief and long-term product vision.
2. [`academic-reports/design-report.pdf`](academic-reports/design-report.pdf) - the Version 0 problem framing, requirements, personas, architecture, and scope decisions.
3. [`academic-reports/development-report.pdf`](academic-reports/development-report.pdf) - implementation history, testing, evaluation, limitations, and proposed future work.
4. [`research/technical-opportunity-assessment.pdf`](research/technical-opportunity-assessment.pdf) - the later Uganda coffee aggregation and traceability opportunity assessment.
5. [`research/white-paper-review/white-paper-critical-review.html`](research/white-paper-review/white-paper-critical-review.html) - an evidence-checked companion review identifying what is credible, what needs correction, and how to make the proposal more useful.
6. [`engineering/`](engineering/) - maintained technical references for the current codebase.
7. [`evidence/`](evidence/) - screenshots, diagrams, wireframes, and generated report samples.

## Directory structure

```text
docs/
├── academic-reports/       Assessed university design and development reports
├── engineering/            Current technical and maintenance documentation
├── evidence/
│   ├── current-screenshots/ Current application walkthrough
│   ├── generated-reports/  PDFs produced by the application
│   └── submission-assets/  Diagrams, mockups, and snapshots used in the reports
├── research/               Post-project opportunity and feasibility research
└── source-material/        Original stakeholder material; not portfolio-ready
```

The files in `evidence/submission-assets/project-notes/` are historical snapshots packaged with the academic submission. The maintained versions are in `engineering/`.

## Scope and chronology

The original dossier describes a broad future system spanning USSD/SMS, offline Android, web administration, group purchasing, group selling, traceability, compliance, payments, and multiple roles.

The academic reports document a deliberate Version 0 decision to implement one coherent workflow for one primary user: the cooperative aggregator. Farmer-direct and buyer-direct interfaces, authentication, PostgreSQL, offline operation, and summative user testing were explicitly deferred. Flask, SQLite, and server-rendered pages were selected to reduce implementation overhead during a 25-day individual project.

The technical opportunity assessment was produced later. It narrows the early organisational role toward farmer registration, plot/GPS data custody, field verification, lot assembly, and buyer-facing documentation, while recommending partnerships for physical collection-hub operations.

## Publication and privacy

- The original dossier photographs retain phone EXIF metadata, including GPS data. They are ignored by Git and should remain private unless sanitized.
- The academic reports contain the author's student number. Redact it before using the PDFs on a public portfolio site.
- Generated reports use synthetic demo data, but they should still be reviewed before publication.
- Current screenshots are preferable to the older academic-submission screenshots when presenting the latest interface.
