# RetailSignal — Case Study Presentation Outline

## Slide 1 — Executive question

**RetailSignal: E-commerce Revenue, Customer Retention & Market Performance Intelligence**

State the decision context and source period after verified ingestion. Do not place unverified KPI cards or fabricated chart values on the slide.

## Slide 2 — Source and quality

- Official UCI Online Retail II attribution and GBP currency.
- Rows, date range, missing identifiers, duplicates, negative quantities, cancellation-prefixed invoice records, invalid values and invoice consistency — fill from the generated audit.
- State the handling decision for each issue and show that line-level records were preserved.

## Slide 3 — Definitions and model

- Define signed line value, gross positive line sales, eligible sales invoice, identified customer, and cancellation-prefix flag.
- Show pipeline diagram and source-row grain.
- Explain why recorded sales is not profit.

## Slide 4 — Sales performance

- Monthly eligible positive sales, signed recorded value, and invoice volume.
- Annotate only verified peaks/troughs and compare month-level values with volume.
- Distinguish full from partial months.

## Slide 5 — Product and market concentration

- Pareto ranking for products; country contribution chart.
- State denominators and missing-label coverage.
- Add sensitivity or concentration measure only if computed and reviewed.

## Slide 6 — Customer analytics

- Repeat-purchase definition and denominator.
- Cohort table with unequal observation windows clearly marked.
- RFM score rules and behavioral—not intent-based—segment labels.

## Slide 7 — Cancellations and data risks

- Trend and distribution of cancellation-prefixed invoices, negative quantities, and negative signed lines.
- State that source patterns do not prove physical return completion.

## Slide 8 — Statistical robustness and limitations

- Pre-specified tests, effect sizes/p-values, sample sizes, assumptions, limits.
- Identify which differences remain robust to definitions and data-quality sensitivity checks.

## Slide 9 — Business decisions

- Three to five recommendations tied to measured findings, queries, addressable populations, uncertainty, and proposed success metrics.
- Include explicit data needs for margin, CAC, and campaign ROI.

## Slide 10 — Reproduction and personal contribution

- GitHub repo, Windows setup commands, tests, PostgreSQL model/queries, notebook and Power BI verification.
- List only components actually implemented and executed.
