# Data Cleaning & Reporting Automation

## About the Project
This project automates the process of taking raw business data from CSV or Excel files, cleaning and standardizing it, and preparing it for analysis and reporting. It removes common data quality issues, produces before-and-after quality audit reports, and exports clean datasets ready for Power BI visualization.

## Technologies Used
- Python
- Pandas and NumPy
- OpenPyXL and XlsxWriter
- SQLite
- Streamlit and Plotly
- Power BI

## Main Features
- **File Ingestion**: Supports both CSV and Excel (.xlsx, .xls) files.
- **Data Cleaning**: Removes duplicates, handles missing values, corrects negative numbers, and strips extra whitespace.
- **Standardization**: Converts multiple date formats into standard YYYY-MM-DD format and unifies category names and casing.
- **Outlier Flagging**: Identifies numerical outliers using the Interquartile Range (IQR) method without deleting records.
- **Quality Auditing**: Compares data quality before and after cleaning, generating both Excel and HTML summary reports.
- **Business Metrics**: Calculates total revenue, average order value, units sold, monthly trends, and category breakdowns.
- **Multiple Exports**: Saves outputs to cleaned CSV, formatted Excel, SQLite database, and a multi-sheet Excel file for Power BI.
- **Interactive Web App**: Includes a Streamlit interface for file uploading, metric exploration, and one-click downloads.

## What I Learned
- Data cleaning and preprocessing techniques using Pandas and NumPy
- Detecting and resolving data issues such as missing values, duplicate rows, and inconsistent date formats
- Structuring a modular Python project with separate modules for configuration, cleaning, validation, and reporting
- Generating formatted multi-sheet Excel workbooks and reports programmatically
- Creating an interactive web interface with Streamlit for data display
- Preparing structured datasets for easy import and dashboard creation in Power BI

## Project Workflow
1. **Load Data**: Ingest raw CSV or Excel dataset and check its initial shape.
2. **Quality Profiling (Before)**: Count missing values, duplicates, and check column data types.
3. **Cleaning and Transformation**: Normalize column headers, drop critical null rows, standardize dates, harmonize text, and fill remaining missing cells.
4. **Validation (After)**: Run quality checks to confirm completeness and verify that no critical nulls or duplicates remain.
5. **Business Metrics**: Compute summary KPIs, monthly aggregations, and category totals.
6. **Report Generation and Export**: Save the cleaned dataset, quality audit report, business metrics workbook, SQLite table, and Power BI data model.

## Project Structure
```
Data Cleaning & Reporting Automation/
├── data/
│   ├── raw/                  # Input folder for raw files
│   ├── cleaned/              # Output folder for cleaned datasets and SQLite database
│   └── sample/               # Sample sales dataset for testing
├── reports/
│   ├── data_quality_report.xlsx   # Before/after data quality audit
│   ├── business_metrics.xlsx      # Calculated metrics and charts
│   └── html/                      # Web-viewable quality report
├── powerbi/
│   └── dashboard_data.xlsx        # 6-sheet workbook modeled for Power BI
├── src/
│   ├── config.py             # Settings, column mappings, and rules
│   ├── loader.py             # File loading and format detection
│   ├── validator.py          # Data profiling functions
│   ├── cleaner.py            # Core 10-step cleaning logic
│   ├── standardizer.py       # Post-cleaning validation checks
│   ├── metrics.py            # Business KPI calculations
│   ├── reporter.py           # Excel and HTML report generators
│   └── exporter.py           # Output file writers
├── tests/
│   └── test_pipeline.py      # Automated unit tests
├── main.py                   # Command-line entry point
├── app.py                    # Streamlit web application
├── run_app.bat               # Windows batch launcher for the web app
├── generate_sample_data.py   # Script to generate sample test data
└── requirements.txt          # Required Python packages
```

## How to Run the Project

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate sample data (optional)
```bash
python generate_sample_data.py
```

### 3. Run via Web Application
```bash
streamlit run app.py
```
*(On Windows, you can also double-click `run_app.bat`)*

### 4. Run via Command Line
```bash
# Process the sample data
python main.py --input data/sample/sample_sales_data.csv

# Or place your file in data/raw/ and run:
python main.py
```

### 5. Open in Power BI
1. Open Power BI Desktop.
2. Select **Get Data** > **Excel Workbook**.
3. Choose `powerbi/dashboard_data.xlsx`.
4. Select the tables (`CleanedData`, `MetricsSummary`, `MonthlyTrend`, `CategoryBreakdown`, `RegionBreakdown`, `StatusBreakdown`) and load them into your report.

## Future Improvements
- Connect directly to SQL databases for automated data extraction
- Add custom threshold adjustments directly inside the web interface
- Add email delivery for scheduled quality and metrics reports

## Author
Harini R.
