# Business Recommendations — Evidence Gate Required

**No business recommendations are yet presented as findings.** The source workbook was not available for analysis during initial creation. The actions below are the decision protocol to apply *after* actual results have been measured, not claims that a particular issue exists in this dataset.

## Prioritization protocol

Select three to five recommendations only after each candidate is supported by a reproducible calculation and passes a data-quality review. Rank candidates by estimated commercial relevance, size of the addressable population, stability under alternate definitions, feasibility, and measurability—not by a visually dramatic chart.

For every chosen recommendation, complete the following record:

| Field | Required content |
|---|---|
| Observation | Exact measured result, period, population, denominator, and currency |
| Calculation | File/query, formula, filters, and row/customer/invoice grain |
| Business importance | Why this amount or behavior could change a decision |
| Proposed action | Small, reversible investigation or pilot; no inferred intent from RFM alone |
| Uncertainty | Missing identifiers, partial periods, outlier/duplicate sensitivity, sample size, alternatives |
| Success evidence | Predefined KPI, comparison period/control group where feasible, guardrail metrics, and review date |
| Further data | Cost, campaign, customer acquisition, refund, or operational fields required |

## Hypotheses to evaluate after analysis

1. **Product concentration:** if eligible sales are heavily concentrated, evaluate stock availability/service risk for high-contribution products and compare any assortment changes against a baseline. Confirm with product margin and stockout data before prioritizing by profitability.
2. **Observed customer repeat activity:** if identifiable customers show materially different repeat-purchase patterns by cohort, investigate onboarding or re-engagement opportunities. Missing IDs and unequal cohort ages must be quantified first; validate a campaign with randomized or carefully matched comparisons.
3. **Country opportunity:** if countries differ meaningfully in positive recorded sales per invoice and customer coverage, investigate operational access and shipping economics before expansion. The source has no country-specific cost or acquisition data.
4. **Negative-line/cancellation patterns:** if specific time periods or invoice groups show unusual changes, trace a sample to order-management and refund records before changing policy. Prefix/quantity flags do not prove physical returns or customer dissatisfaction.
5. **Data capture:** if missing identifiers materially limit customer reporting, assess at which workflow stage IDs are missing. Do not infer that all anonymous rows came from unique customers or merge them to identified records without evidence.

## Completion rule

Delete any hypothesis that the real data does not support. Avoid language such as “increase retention by X%,” “improve profit,” or “reduce refunds” unless a separate experiment or measured operational comparison supports that claim.
