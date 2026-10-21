"""Pre-specified, cautious statistical checks. Results must be generated from the real dataset."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, mannwhitneyu
from src.config import DEFAULT_CLEANED, PROCESSED_DIR
from src.metrics import build_purchase_invoices


def paired_month_comparison(lines: pd.DataFrame) -> dict:
    """Paired Wilcoxon signed-rank comparison of Jan-Nov 2010 vs Jan-Nov 2011 gross sales."""
    valid = lines.loc[lines["invoice_date"].notna() & lines["is_positive_sales_line"]].copy()
    valid["month"] = pd.to_datetime(valid["invoice_date"]).dt.to_period("M")
    monthly = valid.groupby("month")["line_value"].sum()
    first = {m.month: monthly.get(pd.Period(f"2010-{m.month:02d}", freq="M"), 0.0) for m in [pd.Period(f"2010-{i:02d}", freq="M") for i in range(1, 12)]}
    second = {m.month: monthly.get(pd.Period(f"2011-{m.month:02d}", freq="M"), 0.0) for m in [pd.Period(f"2011-{i:02d}", freq="M") for i in range(1, 12)]}
    paired = pd.DataFrame({"month_number": range(1, 12), "sales_2010": [first[i] for i in range(1, 12)], "sales_2011": [second[i] for i in range(1, 12)]}).dropna()
    if len(paired) < 6 or np.allclose(paired["sales_2011"], paired["sales_2010"]):
        return {"test": "paired Wilcoxon signed-rank", "status": "not_tested", "paired_months": len(paired), "reason": "Fewer than six valid matched months or all paired differences are zero."}
    result = wilcoxon(paired["sales_2011"], paired["sales_2010"], alternative="two-sided", method="auto")
    deltas = paired["sales_2011"] - paired["sales_2010"]
    return {
        "test": "paired Wilcoxon signed-rank", "status": "computed", "periods": "January-November 2010 versus January-November 2011",
        "paired_months": int(len(paired)), "median_monthly_difference_gbp": float(deltas.median()),
        "mean_monthly_difference_gbp": float(deltas.mean()), "statistic": float(result.statistic), "p_value": float(result.pvalue),
        "limitation": "Only 11 calendar-month pairs are available; monthly observations may be dependent, and a small p-value does not establish cause. December is excluded because the 2011 record ends during December."
    }


def customer_spend_comparison(lines: pd.DataFrame) -> dict:
    """Mann-Whitney comparison of per-customer mean order value, one-time vs repeat buyers."""
    purchases = build_purchase_invoices(lines)
    if purchases.empty:
        return {"test": "Mann-Whitney U", "status": "not_tested", "reason": "No eligible identifiable purchase invoices."}
    customer_eligible = (lines["is_customer_analytics_eligible"] if "is_customer_analytics_eligible" in lines.columns
                         else (lines["customer_id"].notna() & lines["invoice_no"].notna()))
    positive = lines.loc[
        lines["is_positive_sales_line"] & customer_eligible
        & lines["customer_id"].notna() & lines["invoice_no"].notna()
        & lines["invoice_date"].notna()
    ].copy()
    orders = positive.groupby(["customer_id", "invoice_no"], as_index=False).agg(order_value_gbp=("line_value", "sum"))
    per_customer = orders.groupby("customer_id", as_index=False).agg(
        frequency_invoices=("invoice_no", "nunique"), mean_positive_order_value_gbp=("order_value_gbp", "mean"),
        total_positive_sales_gbp=("order_value_gbp", "sum"))
    one_time = per_customer.loc[per_customer["frequency_invoices"] == 1, "mean_positive_order_value_gbp"].dropna()
    repeat = per_customer.loc[per_customer["frequency_invoices"] >= 2, "mean_positive_order_value_gbp"].dropna()
    if len(one_time) < 5 or len(repeat) < 5:
        return {"test": "Mann-Whitney U", "status": "not_tested", "one_time_customers": int(len(one_time)), "repeat_customers": int(len(repeat)), "reason": "At least five customers in each group are required by this project's prespecified reporting rule."}
    res = mannwhitneyu(repeat, one_time, alternative="two-sided", method="auto")
    n1, n2 = len(repeat), len(one_time)
    rank_biserial = 2 * res.statistic / (n1 * n2) - 1
    return {
        "test": "Mann-Whitney U", "status": "computed", "groups": "Per-customer mean positive order value: repeat purchasers (2+ eligible invoices) vs one-time purchasers (1 eligible invoice)",
        "one_time_customers": int(n2), "repeat_customers": int(n1),
        "median_one_time_customer_mean_order_value_gbp": float(one_time.median()),
        "median_repeat_customer_mean_order_value_gbp": float(repeat.median()),
        "u_statistic": float(res.statistic), "p_value": float(res.pvalue), "rank_biserial_effect_size": float(rank_biserial),
        "limitation": "This is an observational customer-level comparison. Repeat status is based on the same historical window; right-censoring, customer tenure, customer heterogeneity, and multiple comparisons limit interpretation. It does not show that repeat purchasing causes larger orders."
    }


def run_statistical_checks(input_path: str | Path = DEFAULT_CLEANED, output_dir: str | Path = PROCESSED_DIR) -> dict:
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Cleaned data not found: {input_path}")
    lines = pd.read_csv(input_path, low_memory=False, dtype={"invoice_no": "string", "stock_code": "string", "customer_id": "string", "country": "string"})
    lines["invoice_date"] = pd.to_datetime(lines["invoice_date"], errors="coerce", format="mixed")
    for col in ("quantity", "unit_price", "line_value"):
        lines[col] = pd.to_numeric(lines[col], errors="coerce")
    for col in ("is_cancellation_invoice", "is_positive_sales_line"):
        if lines[col].dtype == object:
            lines[col] = lines[col].astype(str).str.lower().map({"true": True, "false": False})
    results = {"matched_months": paired_month_comparison(lines), "customer_spend_groups": customer_spend_comparison(lines)}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    import json
    (output_dir / "statistical_checks.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return results

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_CLEANED, help="Cleaned line-level CSV")
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR, help="Directory for statistical_checks.json")
    args = parser.parse_args()
    run_statistical_checks(args.input, args.output_dir)


if __name__ == "__main__":
    main()
