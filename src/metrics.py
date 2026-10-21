"""Business metrics and customer analytics for RetailSignal."""
from __future__ import annotations
import numpy as np
import pandas as pd


def _month_start(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M").dt.to_timestamp()


def build_monthly_sales(lines: pd.DataFrame) -> pd.DataFrame:
    valid_dates = lines.loc[lines["invoice_date"].notna()].copy()
    if valid_dates.empty:
        return pd.DataFrame(columns=["month", "net_recorded_sales_gbp", "gross_positive_line_sales_gbp", "negative_line_value_gbp", "recorded_invoices", "sales_invoices", "cancellation_invoices", "line_count"])
    valid_dates["month"] = _month_start(valid_dates["invoice_date"])
    valid_dates["signed_value"] = valid_dates["line_value"].fillna(0)
    valid_dates["positive_sales_value"] = np.where(valid_dates["is_positive_sales_line"], valid_dates["line_value"], 0.0)
    valid_dates["negative_value_abs"] = np.where(valid_dates["line_value"] < 0, -valid_dates["line_value"], 0.0)
    records = []
    for month, group in valid_dates.groupby("month", dropna=True, sort=True):
        sales_invoice_ids = group.loc[group["is_positive_sales_line"], "invoice_no"].dropna().unique()
        records.append({
            "month": month,
            "net_recorded_sales_gbp": float(group["signed_value"].sum()),
            "gross_positive_line_sales_gbp": float(group["positive_sales_value"].sum()),
            "negative_line_value_gbp": float(group["negative_value_abs"].sum()),
            "recorded_invoices": int(group["invoice_no"].nunique(dropna=True)),
            "sales_invoices": int(len(sales_invoice_ids)),
            "cancellation_invoices": int(group.loc[group["is_cancellation_invoice"], "invoice_no"].nunique(dropna=True)),
            "line_count": int(len(group)),
        })
    monthly = pd.DataFrame(records).sort_values("month").reset_index(drop=True)
    # Insert zero-activity calendar months so adjacent rows really are adjacent months.
    if not monthly.empty:
        full_months = pd.date_range(monthly["month"].min(), monthly["month"].max(), freq="MS", name="month")
        monthly = monthly.set_index("month").reindex(full_months).rename_axis("month").reset_index()
        for col in ["net_recorded_sales_gbp", "gross_positive_line_sales_gbp", "negative_line_value_gbp", "recorded_invoices", "sales_invoices", "cancellation_invoices", "line_count"]:
            monthly[col] = monthly[col].fillna(0)
        for col in ["recorded_invoices", "sales_invoices", "cancellation_invoices", "line_count"]:
            monthly[col] = monthly[col].astype("int64")
    monthly["mom_net_sales_change_pct"] = monthly["net_recorded_sales_gbp"].pct_change().replace([np.inf, -np.inf], np.nan) * 100
    monthly["mom_gross_positive_sales_change_pct"] = monthly["gross_positive_line_sales_gbp"].pct_change().replace([np.inf, -np.inf], np.nan) * 100
    monthly["mom_sales_invoice_change_pct"] = monthly["sales_invoices"].pct_change().replace([np.inf, -np.inf], np.nan) * 100
    monthly["average_positive_invoice_value_gbp"] = monthly["gross_positive_line_sales_gbp"] / monthly["sales_invoices"].replace(0, np.nan)
    return monthly


def build_purchase_invoices(lines: pd.DataFrame) -> pd.DataFrame:
    """Invoice-level table of identifiable customer invoices with a qualifying positive line."""
    eligible_customer_line = lines["is_customer_analytics_eligible"] if "is_customer_analytics_eligible" in lines.columns else (lines["customer_id"].notna() & lines["invoice_no"].notna())
    sales = lines.loc[
        lines["is_positive_sales_line"] & eligible_customer_line
        & lines["invoice_date"].notna(),
        ["invoice_no", "customer_id", "invoice_date", "country"],
    ].copy()
    if sales.empty:
        return pd.DataFrame(columns=["invoice_no", "customer_id", "invoice_date", "country", "invoice_month"])
    # If source records assign more than one customer/country/date to an invoice, flag this upstream.
    # Group by both keys so a source invoice assigned to conflicting customers cannot silently
    # become one arbitrarily attributed customer purchase.
    invoices = sales.groupby(["customer_id", "invoice_no"], as_index=False, dropna=False).agg(
        invoice_date=("invoice_date", "min"), country=("country", "min")
    )
    invoices["invoice_month"] = _month_start(invoices["invoice_date"])
    return invoices


def build_customer_rfm(lines: pd.DataFrame, observation_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Compute RFM for identified customers using qualifying purchase invoices.

    Recency and frequency use invoices with at least one positive eligible line.
    Monetary value is signed value on all non-cancellation lines with an identified
    customer; cancellation-prefixed invoices are excluded to avoid treating the
    same reversal as another purchase. All values are recorded GBP, not profit.
    """
    purchases = build_purchase_invoices(lines)
    if purchases.empty:
        return pd.DataFrame(columns=["customer_id", "recency_days", "frequency_invoices", "monetary_recorded_gbp", "first_purchase_date", "last_purchase_date", "r_score", "f_score", "m_score", "rfm_score", "segment"])
    max_date = pd.to_datetime(lines["invoice_date"], errors="coerce").max()
    if observation_date is None:
        if pd.isna(max_date):
            return pd.DataFrame()
        observation_date = max_date.normalize() + pd.Timedelta(days=1)
    else:
        observation_date = pd.Timestamp(observation_date).normalize()
    purchase_features = purchases.groupby("customer_id").agg(
        frequency_invoices=("invoice_no", "nunique"),
        first_purchase_date=("invoice_date", "min"),
        last_purchase_date=("invoice_date", "max"),
    )
    purchase_features["recency_days"] = (observation_date - purchase_features["last_purchase_date"].dt.normalize()).dt.days
    customer_eligible = lines["is_customer_analytics_eligible"] if "is_customer_analytics_eligible" in lines.columns else lines["customer_id"].notna()
    monetary = lines.loc[
        customer_eligible & ~lines["is_cancellation_invoice"] & lines["line_value"].notna()
    ].groupby("customer_id")["line_value"].sum().rename("monetary_recorded_gbp")
    features = purchase_features.join(monetary, how="left").fillna({"monetary_recorded_gbp": 0.0}).reset_index()
    features["r_score"] = _quintile_score(features["recency_days"], lower_is_better=True)
    features["f_score"] = _quintile_score(features["frequency_invoices"], lower_is_better=False)
    features["m_score"] = _quintile_score(features["monetary_recorded_gbp"], lower_is_better=False)
    features["rfm_score"] = features[["r_score", "f_score", "m_score"]].astype(int).astype(str).agg("".join, axis=1)
    features["segment"] = features.apply(_rfm_segment, axis=1)
    features["observation_date"] = observation_date
    return features.sort_values(["segment", "monetary_recorded_gbp"], ascending=[True, False]).reset_index(drop=True)


def _quintile_score(values: pd.Series, lower_is_better: bool) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce")
    if values.notna().sum() < 5:
        return pd.Series(3, index=values.index, dtype="int64")
    ranks = values.rank(method="first", ascending=True)
    scores = pd.qcut(ranks, q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    if lower_is_better:
        scores = 6 - scores
    return scores.astype("int64")


def _rfm_segment(row: pd.Series) -> str:
    r, f, m = int(row["r_score"]), int(row["f_score"]), int(row["m_score"])
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions (behavioral)"
    if f >= 4 and m >= 3:
        return "Frequent / higher value"
    if r >= 4 and f <= 2:
        return "Recent / low frequency"
    if r <= 2 and f >= 3:
        return "At-risk frequent"
    if r <= 2 and f <= 2:
        return "Inactive / low frequency"
    if m >= 4:
        return "Higher monetary / mixed activity"
    return "Regular / developing"


def build_rfm_sensitivity(lines: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare baseline signed RFM monetary values with positive-sales-only monetary values."""
    baseline = build_customer_rfm(lines)
    if baseline.empty:
        empty = pd.DataFrame()
        return empty, pd.DataFrame([{"comparison": "signed vs positive-only monetary", "customers": 0,
                                    "m_score_changed_count": 0, "m_score_changed_pct": None,
                                    "segment_changed_count": 0, "segment_changed_pct": None}])
    customer_eligible = lines["is_customer_analytics_eligible"] if "is_customer_analytics_eligible" in lines.columns else lines["customer_id"].notna()
    positive_monetary = lines.loc[
        customer_eligible & lines["is_positive_sales_line"] & lines["customer_id"].notna()
    ].groupby("customer_id")["line_value"].sum().rename("monetary_positive_only_gbp")
    result = baseline.merge(positive_monetary, on="customer_id", how="left", validate="one_to_one")
    result["monetary_positive_only_gbp"] = result["monetary_positive_only_gbp"].fillna(0.0)
    result["m_score_positive_only"] = _quintile_score(result["monetary_positive_only_gbp"], lower_is_better=False).to_numpy()
    alt_rows = result.copy()
    alt_rows["m_score"] = alt_rows["m_score_positive_only"]
    result["segment_positive_only_monetary"] = alt_rows.apply(_rfm_segment, axis=1)
    result["m_score_changed"] = result["m_score"].astype(int) != result["m_score_positive_only"].astype(int)
    result["segment_changed"] = result["segment"] != result["segment_positive_only_monetary"]
    n = len(result)
    summary = pd.DataFrame([{
        "comparison": "signed vs positive-only monetary",
        "customers": n,
        "m_score_changed_count": int(result["m_score_changed"].sum()),
        "m_score_changed_pct": float(result["m_score_changed"].mean() * 100),
        "segment_changed_count": int(result["segment_changed"].sum()),
        "segment_changed_pct": float(result["segment_changed"].mean() * 100),
        "baseline_monetary_definition": "Signed line value on eligible non-cancellation rows for identifiable customers",
        "alternative_monetary_definition": "Sum only eligible positive sales lines for identifiable customers",
    }])
    return result, summary


def build_cohort_retention(lines: pd.DataFrame) -> pd.DataFrame:
    """Long-format monthly cohort activity with explicit cohort sizes and elapsed months."""
    purchases = build_purchase_invoices(lines)
    if purchases.empty:
        return pd.DataFrame(columns=["cohort_month", "activity_month", "cohort_index", "active_customers", "cohort_size", "retention_rate"])
    purchases["cohort_month"] = purchases.groupby("customer_id")["invoice_month"].transform("min")
    activity = purchases.groupby(["cohort_month", "invoice_month"], as_index=False).agg(active_customers=("customer_id", "nunique"))
    cohort_sizes = purchases.groupby("cohort_month")["customer_id"].nunique().rename("cohort_size")
    activity = activity.join(cohort_sizes, on="cohort_month")
    activity["cohort_index"] = (
        (activity["invoice_month"].dt.year - activity["cohort_month"].dt.year) * 12
        + activity["invoice_month"].dt.month - activity["cohort_month"].dt.month + 1
    ).astype(int)
    activity["retention_rate"] = activity["active_customers"] / activity["cohort_size"]
    return activity.rename(columns={"invoice_month": "activity_month"}).sort_values(["cohort_month", "cohort_index"]).reset_index(drop=True)


def build_product_performance(lines: pd.DataFrame) -> pd.DataFrame:
    eligible = lines.loc[lines["is_positive_sales_line"] & lines["stock_code"].notna()].copy()
    if eligible.empty:
        return pd.DataFrame(columns=["stock_code", "description", "gross_positive_line_sales_gbp", "units_sold_positive", "invoice_count", "sales_contribution_pct", "cumulative_contribution_pct"])
    result = eligible.groupby("stock_code", as_index=False).agg(
        description=("description", lambda x: x.dropna().mode().iloc[0] if not x.dropna().mode().empty else pd.NA),
        gross_positive_line_sales_gbp=("line_value", "sum"),
        units_sold_positive=("quantity", "sum"),
        invoice_count=("invoice_no", "nunique"),
    ).sort_values("gross_positive_line_sales_gbp", ascending=False).reset_index(drop=True)
    total = result["gross_positive_line_sales_gbp"].sum()
    result["sales_contribution_pct"] = result["gross_positive_line_sales_gbp"] / total * 100 if total else np.nan
    result["cumulative_contribution_pct"] = result["sales_contribution_pct"].cumsum()
    return result


def build_country_performance(lines: pd.DataFrame) -> pd.DataFrame:
    eligible = lines.loc[lines["is_positive_sales_line"] & lines["country"].notna()].copy()
    if eligible.empty:
        return pd.DataFrame(columns=["country", "gross_positive_line_sales_gbp", "units_sold_positive", "invoice_count", "identified_customers", "sales_contribution_pct"])
    result = eligible.groupby("country", as_index=False).agg(
        gross_positive_line_sales_gbp=("line_value", "sum"),
        units_sold_positive=("quantity", "sum"),
        invoice_count=("invoice_no", "nunique"),
        identified_customers=("customer_id", "nunique"),
    ).sort_values("gross_positive_line_sales_gbp", ascending=False).reset_index(drop=True)
    total = result["gross_positive_line_sales_gbp"].sum()
    result["sales_contribution_pct"] = result["gross_positive_line_sales_gbp"] / total * 100 if total else np.nan
    return result


def build_cancellation_summary(lines: pd.DataFrame) -> pd.DataFrame:
    """Report overlapping diagnostics independently; counts across rows are not additive."""
    checks = [
        ("Cancellation-prefixed invoice rows", lines["is_cancellation_invoice"]),
        ("Negative quantity rows", lines["quantity"] < 0),
        ("Negative signed line-value rows", lines["line_value"] < 0),
        ("Nonpositive unit-price rows", lines["unit_price"] <= 0),
        ("Exact duplicate candidate extra rows", lines["is_exact_duplicate_extra_row"]),
    ]
    rows = []
    for label, mask in checks:
        selected = lines.loc[mask.fillna(False)]
        rows.append({
            "diagnostic": label,
            "rows": int(len(selected)),
            "invoices": int(selected["invoice_no"].nunique(dropna=True)),
            "signed_line_value_gbp": float(selected["line_value"].sum(skipna=True)),
            "absolute_negative_value_gbp": float(-selected.loc[selected["line_value"] < 0, "line_value"].sum()),
        })
    result = pd.DataFrame(rows)
    result["counts_overlap"] = True
    return result


def build_customer_concentration(lines: pd.DataFrame) -> pd.DataFrame:
    """Rank positive sales contribution among customers with reliable identifiers."""
    customer_eligible = lines["is_customer_analytics_eligible"] if "is_customer_analytics_eligible" in lines.columns else lines["customer_id"].notna()
    eligible = lines.loc[customer_eligible & lines["is_positive_sales_line"] & lines["customer_id"].notna()].copy()
    if eligible.empty:
        return pd.DataFrame(columns=["customer_id", "gross_positive_line_sales_gbp", "eligible_invoices", "sales_rank", "sales_contribution_pct", "cumulative_contribution_pct", "cumulative_customer_pct"])
    result = eligible.groupby("customer_id", as_index=False).agg(
        gross_positive_line_sales_gbp=("line_value", "sum"),
        eligible_invoices=("invoice_no", "nunique"),
    ).sort_values(["gross_positive_line_sales_gbp", "customer_id"], ascending=[False, True]).reset_index(drop=True)
    total = result["gross_positive_line_sales_gbp"].sum()
    result["sales_rank"] = np.arange(1, len(result) + 1)
    result["sales_contribution_pct"] = result["gross_positive_line_sales_gbp"] / total * 100 if total else np.nan
    result["cumulative_contribution_pct"] = result["sales_contribution_pct"].cumsum()
    result["cumulative_customer_pct"] = result["sales_rank"] / len(result) * 100
    return result


def build_rfm_segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    """Summarize observed customer features by rule-based RFM segment."""
    cols = ["segment", "customers", "segment_share_pct", "median_recency_days", "median_frequency_invoices", "mean_frequency_invoices", "median_monetary_recorded_gbp", "mean_monetary_recorded_gbp"]
    if rfm.empty:
        return pd.DataFrame(columns=cols)
    total = len(rfm)
    result = rfm.groupby("segment", as_index=False).agg(
        customers=("customer_id", "nunique"),
        median_recency_days=("recency_days", "median"),
        median_frequency_invoices=("frequency_invoices", "median"),
        mean_frequency_invoices=("frequency_invoices", "mean"),
        median_monetary_recorded_gbp=("monetary_recorded_gbp", "median"),
        mean_monetary_recorded_gbp=("monetary_recorded_gbp", "mean"),
    ).sort_values("customers", ascending=False).reset_index(drop=True)
    result["segment_share_pct"] = result["customers"] / total * 100
    return result[cols]


def build_duplicate_sensitivity(lines: pd.DataFrame) -> pd.DataFrame:
    """Quantify how flagged exact-duplicate extras change core totals, without deleting them."""
    baseline = lines.copy()
    flag = baseline["is_exact_duplicate_extra_row"].fillna(False).astype(bool)
    alternative = baseline.loc[~flag].copy()

    def values(frame: pd.DataFrame) -> dict[str, float]:
        purchases = build_purchase_invoices(frame)
        frequency = purchases.groupby("customer_id")["invoice_no"].nunique() if not purchases.empty else pd.Series(dtype=int)
        customer_count = int(len(frequency))
        repeat_count = int((frequency >= 2).sum()) if customer_count else 0
        return {
            "source_rows": float(len(frame)),
            "exact_duplicate_extra_rows_included": float(frame["is_exact_duplicate_extra_row"].fillna(False).sum()),
            "net_recorded_sales_gbp": float(frame["line_value"].sum(skipna=True)),
            "gross_positive_line_sales_gbp": float(frame.loc[frame["is_positive_sales_line"], "line_value"].sum(skipna=True)),
            "negative_line_value_magnitude_gbp": float(-frame.loc[frame["line_value"] < 0, "line_value"].sum(skipna=True)),
            "recorded_invoice_count": float(frame["invoice_no"].nunique(dropna=True)),
            "eligible_sales_invoice_count": float(frame.loc[frame["is_positive_sales_line"], "invoice_no"].nunique(dropna=True)),
            "identified_customers_with_purchase": float(customer_count),
            "repeat_customers": float(repeat_count),
            "repeat_customer_rate_pct": float(repeat_count / customer_count * 100) if customer_count else np.nan,
        }

    base = values(baseline)
    alt = values(alternative)
    rows = []
    for metric, baseline_value in base.items():
        alt_value = alt[metric]
        delta = alt_value - baseline_value if pd.notna(alt_value) and pd.notna(baseline_value) else np.nan
        pct_delta = delta / baseline_value * 100 if pd.notna(delta) and baseline_value != 0 else np.nan
        rows.append({"metric": metric, "baseline_all_rows": baseline_value,
                     "sensitivity_excluding_duplicate_extras": alt_value,
                     "absolute_difference_sensitivity_minus_baseline": delta,
                     "pct_difference_sensitivity_vs_baseline": pct_delta})
    return pd.DataFrame(rows)
