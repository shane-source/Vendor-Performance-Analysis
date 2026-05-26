# =============================================================================
# get_vendor_summary.py  —  STEP 2: Build the master vendor summary table
# =============================================================================
# What this script does:
#   - Reads all raw tables from inventory.db
#   - Merges purchases, prices, and sales into one clean master table
#   - Calculates vendor-level KPIs:
#       • Total purchases, total sales, profit margin
#       • Purchase price variance
#       • Stock turnover
#       • Top vs low performing vendors
#   - Saves the summary back to inventory.db as 'vendor_summary'
#   - Exports it to powerbi/vendor_summary.csv  (ready for Power BI)
#   - Logs everything to logs/vendor_summary.log
# =============================================================================

import os
import logging
import pandas as pd
from sqlalchemy import create_engine

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR   = os.path.join(BASE_DIR, "logs")
DB_PATH   = os.path.join(BASE_DIR, "inventory.db")
PBI_DIR   = os.path.join(BASE_DIR, "powerbi")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(PBI_DIR, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename = os.path.join(LOG_DIR, "vendor_summary.log"),
    level    = logging.DEBUG,
    format   = "%(asctime)s | %(levelname)-8s | %(message)s",
    filemode = "a",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
logging.getLogger("").addHandler(console)

engine = create_engine(f"sqlite:///{DB_PATH}")
logging.info("Connected to: %s", DB_PATH)


# =============================================================================
# HELPER: safe read
# =============================================================================
def read_table(table_name):
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        logging.info("Loaded '%-25s'  %d rows", table_name, len(df))
        return df
    except Exception as e:
        logging.warning("Could not load '%s': %s", table_name, e)
        return pd.DataFrame()


# =============================================================================
# STEP 1 — Load raw tables
# =============================================================================
logging.info("=" * 60)
logging.info("BUILDING VENDOR SUMMARY")
logging.info("=" * 60)

purchases       = read_table("purchases")
purchase_prices = read_table("purchase_prices")
sales           = read_table("vendor_sales_summary")
begin_inv       = read_table("begin_inventory")
end_inv         = read_table("end_inventory")
invoices        = read_table("vendor_invoice")

# Print all columns so we know what we're working with
for name, df in [("purchases", purchases), ("purchase_prices", purchase_prices),
                 ("vendor_sales_summary", sales), ("begin_inventory", begin_inv),
                 ("end_inventory", end_inv), ("vendor_invoice", invoices)]:
    logging.debug("'%s' columns: %s", name, list(df.columns))


# =============================================================================
# STEP 2 — Standardise column names
# =============================================================================
def normalise_cols(df):
    """Strip whitespace, lowercase, replace spaces with underscores."""
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df

purchases       = normalise_cols(purchases)
purchase_prices = normalise_cols(purchase_prices)
sales           = normalise_cols(sales)
begin_inv       = normalise_cols(begin_inv)
end_inv         = normalise_cols(end_inv)
invoices        = normalise_cols(invoices)

logging.info("Column names normalised.")


# =============================================================================
# STEP 3 — Build vendor purchase summary
# =============================================================================
logging.info("Building vendor purchase summary...")

# Detect key columns dynamically
def find_col(df, *keywords):
    for kw in keywords:
        for col in df.columns:
            if kw.lower() in col.lower():
                return col
    return None

# purchases table key columns
vendor_col_p  = find_col(purchases, "vendor_name", "vendor", "supplier")
qty_col       = find_col(purchases, "quantity", "qty", "purchases")
price_col_p   = find_col(purchases, "purchaseprice", "purchase_price", "price", "unit_price")
dollars_col   = find_col(purchases, "dollars", "total", "amount", "spend")
brand_col     = find_col(purchases, "brand", "product", "description", "item")
classification_col = find_col(purchases, "classification", "category", "type")

logging.info("purchases — vendor:%s  qty:%s  price:%s  dollars:%s",
             vendor_col_p, qty_col, price_col_p, dollars_col)

# purchase_prices key columns
vendor_col_pp = find_col(purchase_prices, "vendor_name", "vendor", "supplier")
price_col_pp  = find_col(purchase_prices, "price", "purchaseprice", "unit_price")
volume_col    = find_col(purchase_prices, "volume", "qty", "quantity")

logging.info("purchase_prices — vendor:%s  price:%s  volume:%s",
             vendor_col_pp, price_col_pp, volume_col)

# ── Purchase totals per vendor ────────────────────────────────────────────────
if vendor_col_p and dollars_col and qty_col:
    purchase_summary = (
        purchases
        .groupby(vendor_col_p)
        .agg(
            total_purchases_dollars = (dollars_col, "sum"),
            total_quantity_purchased = (qty_col, "sum"),
            number_of_purchases      = (qty_col, "count"),
        )
        .reset_index()
        .rename(columns={vendor_col_p: "vendor_name"})
    )
    purchase_summary["avg_purchase_price"] = (
        purchase_summary["total_purchases_dollars"] /
        purchase_summary["total_quantity_purchased"]
    ).round(2)
    logging.info("Purchase summary built: %d vendors", len(purchase_summary))
else:
    logging.warning("Could not build purchase summary — missing columns")
    purchase_summary = pd.DataFrame()


# =============================================================================
# STEP 4 — Build vendor sales summary
# =============================================================================
logging.info("Building vendor sales summary...")

vendor_col_s  = find_col(sales, "vendor_name", "vendor", "supplier")
# FIX: search for dollar/amount columns BEFORE quantity columns
# The old order accidentally matched "totalsalesquantity" as the sales dollars column
sales_col     = find_col(sales, "saledollars", "sale_dollars", "totalsales", "salestotal",
                          "revenue", "amount", "dollars")
sales_qty_col = find_col(sales, "salequantity", "sale_quantity", "qty_sold", "quantity_sold",
                          "totalsalesquantity")

# Extra safety: if detected sales_col looks like a quantity column, clear it
if sales_col and any(kw in sales_col.lower() for kw in ["quantity", "qty", "units"]):
    logging.warning("sales_col '%s' looks like a quantity column — resetting to None", sales_col)
    sales_col = None
excise_col    = find_col(sales, "exciseduty", "excise", "tax", "duty")

logging.info("sales — vendor:%s  sales_dollars:%s  sales_qty:%s",
             vendor_col_s, sales_col, sales_qty_col)

if vendor_col_s and sales_col:
    agg_dict = {
        "total_sales_dollars"  : (sales_col, "sum"),
    }
    if sales_qty_col:
        agg_dict["total_quantity_sold"] = (sales_qty_col, "sum")
    if excise_col:
        agg_dict["total_excise_duty"] = (excise_col, "sum")

    sales_summary = (
        sales
        .groupby(vendor_col_s)
        .agg(**{k: pd.NamedAgg(*v) for k, v in agg_dict.items()})
        .reset_index()
        .rename(columns={vendor_col_s: "vendor_name"})
    )
    logging.info("Sales summary built: %d vendors", len(sales_summary))
else:
    logging.warning("Could not build sales summary — missing columns")
    sales_summary = pd.DataFrame()


# =============================================================================
# STEP 5 — Merge into master vendor summary
# =============================================================================
logging.info("Merging into master vendor summary...")

if not purchase_summary.empty and not sales_summary.empty:
    vendor_summary = pd.merge(
        purchase_summary, sales_summary,
        on="vendor_name", how="outer"
    )
elif not purchase_summary.empty:
    vendor_summary = purchase_summary.copy()
elif not sales_summary.empty:
    vendor_summary = sales_summary.copy()
else:
    logging.error("Both purchase and sales summaries are empty — cannot build master table")
    vendor_summary = pd.DataFrame()

logging.info("Master summary: %d vendors after merge", len(vendor_summary))


# =============================================================================
# STEP 6 — KPI calculations
# =============================================================================
if not vendor_summary.empty:
    logging.info("Calculating KPIs...")

    # Gross profit and margin
    if "total_sales_dollars" in vendor_summary.columns and "total_purchases_dollars" in vendor_summary.columns:
        vendor_summary["gross_profit"] = (
            vendor_summary["total_sales_dollars"] - vendor_summary["total_purchases_dollars"]
        ).round(2)
        vendor_summary["profit_margin_pct"] = (
            vendor_summary["gross_profit"] / vendor_summary["total_sales_dollars"].replace(0, pd.NA) * 100
        ).round(2)

    # Purchase price variance vs average
    if "avg_purchase_price" in vendor_summary.columns:
        fleet_avg_price = vendor_summary["avg_purchase_price"].mean()
        vendor_summary["price_variance_vs_avg"] = (
            vendor_summary["avg_purchase_price"] - fleet_avg_price
        ).round(2)
        vendor_summary["price_variance_pct"] = (
            vendor_summary["price_variance_vs_avg"] / fleet_avg_price * 100
        ).round(2)

    # Sales-to-purchase ratio (efficiency metric)
    if "total_sales_dollars" in vendor_summary.columns and "total_purchases_dollars" in vendor_summary.columns:
        vendor_summary["sales_to_purchase_ratio"] = (
            vendor_summary["total_sales_dollars"] /
            vendor_summary["total_purchases_dollars"].replace(0, pd.NA)
        ).round(2)

    # Vendor classification: Top vs Low performer
    # FIX: use pd.notna() before comparing — NA >= number raises TypeError
    if "profit_margin_pct" in vendor_summary.columns:
        median_margin = vendor_summary["profit_margin_pct"].median()
        vendor_summary["vendor_tier"] = vendor_summary["profit_margin_pct"].apply(
            lambda x: "Top Performer" if pd.notna(x) and x >= median_margin
                      else ("Low Performer" if pd.notna(x) else "Unknown")
        )
        logging.info("Median profit margin: %.2f%%", median_margin)
        logging.info("Top performers: %d  |  Low performers: %d",
                     (vendor_summary["vendor_tier"]=="Top Performer").sum(),
                     (vendor_summary["vendor_tier"]=="Low Performer").sum())

    # Sort by gross profit descending
    if "gross_profit" in vendor_summary.columns:
        vendor_summary.sort_values("gross_profit", ascending=False, inplace=True)
        vendor_summary.reset_index(drop=True, inplace=True)

    logging.info("KPIs calculated. Columns: %s", list(vendor_summary.columns))


# =============================================================================
# STEP 7 — Save to SQLite and export to Power BI
# =============================================================================
if not vendor_summary.empty:
    # Save to SQLite
    vendor_summary.to_sql("vendor_summary", engine, if_exists="replace", index=False)
    logging.info("'vendor_summary' table saved to inventory.db — %d rows", len(vendor_summary))

    # Export CSV for Power BI
    pbi_path = os.path.join(PBI_DIR, "vendor_summary.csv")
    vendor_summary.to_csv(pbi_path, index=False)
    logging.info("Power BI export: %s", pbi_path)

    print(f"\n{'='*55}")
    print(f"  ✅  Vendor summary built — {len(vendor_summary)} vendors")
    print(f"  DB  : inventory.db  →  table: vendor_summary")
    print(f"  CSV : powerbi/vendor_summary.csv  (import into Power BI)")
    print(f"{'='*55}")
    print("\nTop 10 vendors by gross profit:")
    display_cols = [c for c in ["vendor_name","total_purchases_dollars","total_sales_dollars",
                                 "gross_profit","profit_margin_pct","vendor_tier"]
                    if c in vendor_summary.columns]
    print(vendor_summary[display_cols].head(10).to_string(index=False))
    print("\n  Next step: open notebooks/eda.ipynb")

else:
    print("❌ Vendor summary could not be built — check logs/vendor_summary.log")