# Power BI DAX Measure Dictionary

The formulas assume `FactSalesLine` contains a numeric `line_value` field and Boolean `is_positive_sales_line`, `is_cancellation_invoice`, and `is_negative_line_value` fields. Rename references to match the imported model. DAX uses comma argument separators under the standard locale.

```DAX
Net Recorded Sales GBP =
SUM ( FactSalesLine[line_value] )
```

Signed line amounts are summed once. This is recorded transaction value, not profit or cash collected.

```DAX
Gross Positive Line Sales GBP =
CALCULATE (
    SUM ( FactSalesLine[line_value] ),
    FactSalesLine[is_positive_sales_line] = TRUE ()
)
```

```DAX
Negative Line Value Magnitude GBP =
SUMX (
    FILTER ( FactSalesLine, FactSalesLine[line_value] < 0 ),
    - FactSalesLine[line_value]
)
```

This reports the absolute magnitude of negative signed lines as a separate diagnostic; it is not an additional deduction from Net Recorded Sales.

```DAX
Recorded Invoices =
CALCULATE (
    DISTINCTCOUNT ( FactSalesLine[invoice_no] ),
    NOT ISBLANK ( FactSalesLine[invoice_no] )
)

Eligible Sales Invoices =
CALCULATE (
    DISTINCTCOUNT ( FactSalesLine[invoice_no] ),
    FactSalesLine[is_positive_sales_line] = TRUE (),
    NOT ISBLANK ( FactSalesLine[invoice_no] )
)

Average Positive Invoice Value GBP =
DIVIDE ( [Gross Positive Line Sales GBP], [Eligible Sales Invoices] )
```

The denominator is invoice count with at least one qualifying positive line, not every recorded invoice or every line.

```DAX
Identified Customers With Purchase =
COUNTROWS (
    FILTER (
        VALUES ( FactSalesLine[customer_id] ),
        NOT ISBLANK ( FactSalesLine[customer_id] )
            && CALCULATE (
                DISTINCTCOUNT ( FactSalesLine[invoice_no] ),
                FactSalesLine[is_positive_sales_line] = TRUE (),
                FactSalesLine[is_customer_analytics_eligible] = TRUE ()
            ) > 0
    )
)

Repeat Customers =
COUNTROWS (
    FILTER (
        VALUES ( FactSalesLine[customer_id] ),
        NOT ISBLANK ( FactSalesLine[customer_id] )
            && CALCULATE (
                DISTINCTCOUNT ( FactSalesLine[invoice_no] ),
                FactSalesLine[is_positive_sales_line] = TRUE (),
                FactSalesLine[is_customer_analytics_eligible] = TRUE ()
            ) >= 2
    )
)

Repeat-Purchase Customer Rate =
DIVIDE ( [Repeat Customers], [Identified Customers With Purchase] )
```

This rate is calculated for the current filter window. It is not a fixed-cohort retention measure; date slicers can change both first-purchase availability and the observed number of repeat purchases.

```DAX
Cancellation-Prefixed Invoices =
CALCULATE (
    DISTINCTCOUNT ( FactSalesLine[invoice_no] ),
    FactSalesLine[is_cancellation_invoice] = TRUE (),
    NOT ISBLANK ( FactSalesLine[invoice_no] )
)

Negative Quantity Rows =
CALCULATE (
    COUNTROWS ( FactSalesLine ),
    FactSalesLine[quantity] < 0
)

Missing Customer ID Rows =
CALCULATE (
    COUNTROWS ( FactSalesLine ),
    ISBLANK ( FactSalesLine[customer_id] )
)

Missing Customer ID Row Share =
DIVIDE ( [Missing Customer ID Rows], COUNTROWS ( FactSalesLine ) )
```

```DAX
Previous Month Net Recorded Sales GBP =
CALCULATE ( [Net Recorded Sales GBP], DATEADD ( 'Date'[Date], -1, MONTH ) )

MoM Net Recorded Sales Change % =
DIVIDE (
    [Net Recorded Sales GBP] - [Previous Month Net Recorded Sales GBP],
    [Previous Month Net Recorded Sales GBP]
)
```

Use a contiguous marked Date table and validate month context. A zero or absent previous-month value results in blank, which should be displayed as N/A rather than infinity.

## Validation examples

- With no filters, `Net Recorded Sales GBP` must equal `SUM(line_value)` from the fact CSV and SQL fact table.
- With no filters, `Gross Positive Line Sales GBP` must equal the sum of `line_value` where `is_positive_sales_line` is true in Python/SQL.
- On a filter including only C-prefixed invoices, `Gross Positive Line Sales GBP` should be zero by definition.
- `Repeat-Purchase Customer Rate` must lie between 0 and 1 and its denominator excludes blank `CustomerID` values and customers with no qualifying purchase.
- `Negative Line Value Magnitude GBP` should be nonnegative and must not be deducted from signed net value a second time.
- Each monthly result must reconcile with the corresponding month and same filters in `monthly_sales.csv`/SQL.
