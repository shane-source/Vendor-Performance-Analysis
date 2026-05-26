# 📦 Vendor Performance Analysis

> An end-to-end data analytics project analysing vendor performance across purchases, sales, profitability, pricing variance, and inventory — built in Python, SQL, and Power BI.

---

## 📌 Project Overview

Businesses lose money every year through poor vendor management — overpaying suppliers, over-relying on too few vendors, and missing inventory shortfalls before they become stockouts.

This project builds a full analytics pipeline to answer five business questions:

| # | Business Question |
|---|---|
| 1 | Which vendors drive the most sales and gross profit? |
| 2 | Does buying in bulk reduce unit cost? |
| 3 | Which vendors are charging above-average prices but delivering below-average returns? |
| 4 | Is the profit margin gap between top and low performers statistically significant — or just noise? |
| 5 | Which brands are at risk of stockout based on inventory movement? |

---

## 🛠️ Tech Stack

| Tool | How it was used |
|---|---|
| **Python** | Core analysis language |
| **Pandas** | Data manipulation and transformation |
| **NumPy** | Numerical calculations |
| **SQL + SQLite** | Database storage, CTE joins across 7 tables |
| **SQLAlchemy** | Python-to-database engine |
| **Matplotlib + Seaborn** | 8 charts covering distributions, comparisons, trends |
| **SciPy** | Shapiro-Wilk, Levene, Mann-Whitney U hypothesis tests |
| **Power BI** | Interactive dashboard with KPI cards and slicers |
| **Jupyter Notebook** | End-to-end interactive analysis environment |

---

## 📂 Project Structure

```
vendor-performance-analysis/
│
├── notebooks/
│   ├── ingesting_logs.ipynb     ← Load all CSVs into SQLite with chunked reading + logging
│   └── eda.ipynb                ← Full EDA, SQL CTEs, KPIs, charts, hypothesis testing
│
├── scripts/
│   ├── ingest_db.py             ← Script version of ingestion pipeline
│   └── get_vendor_summary.py    ← Builds master vendor KPI table
│
├── .gitignore
└── README.md
```

---

## 📊 Dataset

**Source:** [Kaggle — harshmadhavan/vendor-performance-analysis](https://www.kaggle.com/datasets/harshmadhavan/vendor-performance-analysis)

7 related CSV files:

| File | Description |
|---|---|
| `purchases.csv` | All purchase orders by vendor and brand |
| `purchase_prices.csv` | Unit pricing and volume data |
| `vendor_sales_summary.csv` | Sales by vendor, brand, quantity and dollars |
| `begin_inventory.csv` | Stock on hand at start of period |
| `end_inventory.csv` | Stock on hand at end of period |
| `vendor_invoice.csv` | Invoice records including freight costs |

---

## ⚙️ How to Run

**1. Install dependencies**
```bash
pip install pandas numpy scipy matplotlib seaborn sqlalchemy jupyter
```

**2. Download the dataset from Kaggle and place all CSVs in a `data/` folder**

**3. Run the ingestion notebook**
```bash
jupyter notebook notebooks/ingesting_logs.ipynb
```
This loads all 7 CSVs into `inventory.db`. Large files are automatically read in 50,000-row chunks to avoid memory crashes.

**4. Run the EDA notebook**
```bash
jupyter notebook notebooks/eda.ipynb
```
Run all cells top to bottom.

**5. Import into Power BI**

Open Power BI Desktop → Get Data → Text/CSV → select `powerbi/vendor_summary.csv`

---

## 🔑 Key KPIs

| KPI | How it is calculated |
|---|---|
| **Gross Profit** | Total Sales Dollars − Total Purchase Dollars |
| **Profit Margin %** | (Gross Profit / Total Sales) × 100 |
| **Purchase Price Variance** | Vendor price − fleet average price |
| **Sales-to-Purchase Ratio** | Total Sales / Total Purchases |
| **Vendor Tier** | Top Performer if margin ≥ median, else Low Performer |

---

## 🔬 Hypothesis Testing

**Question:** Is the profit margin difference between Top Performers and Low Performers statistically significant?

```
H₀: No significant difference in profit margins between groups
H₁: There IS a significant difference in profit margins
α  = 0.05
```

**Test selection logic:**
1. **Shapiro-Wilk** — check if data is normally distributed
2. **Levene** — check if variance is equal between groups
3. **Welch t-Test** (if normal) or **Mann-Whitney U** (if not normal)

**Result:** The null hypothesis was rejected. Top performers earn a statistically significantly higher profit margin than low performers (p < 0.05).

---

## 📈 Charts Produced

| # | Chart | Insight |
|---|---|---|
| 1 | Top 20 vendors by total purchases | Who we spend the most with |
| 2 | Top 20 vendors by gross profit | Who actually makes us money |
| 3 | Profit margin distribution | Spread and skew of margins across all brands |
| 4 | Top vs Low performers | Side-by-side KPI comparison by tier |
| 5 | Purchases vs Sales scatter | Profitability position of every vendor |
| 6 | Purchase price variance | Who is charging above and below average |
| 7 | Beginning vs ending inventory | Which brands are at stockout risk |
| 8 | Hypothesis test visualisation | Distribution and box plot comparison |



## 💡 Key Findings

1. **Top 100 vendors account for the majority of gross profit** — concentration risk if any of them are lost
2. **Significant spread in profit margins** — some vendors are far more profitable than others on identical product categories
3. **Top performers earn statistically higher margins** — vendor selection is a key profitability lever, not an interchangeable decision
4. **Several vendors charge above-average prices but generate below-average sales** — clear candidates for contract renegotiation or phase-out
5. **Inventory declined for key brands** — these brands need reorder point reviews to prevent stockouts



---

*Built as a portfolio project to demonstrate end-to-end data analysis skills across Python, SQL, statistical testing, and business intelligence.*
