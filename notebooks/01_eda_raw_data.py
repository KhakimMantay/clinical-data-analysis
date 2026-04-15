import marimo

__generated_with = "0.22.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import marimo as mo

    return mo, pd


@app.cell
def _(pd):
    df = pd.read_csv('../file_index_with_dates.csv')
    df.head()
    return (df,)


@app.cell
def _(df):
    print(df.shape)
    return


@app.cell
def _(df):
    df.info()
    return


@app.cell(hide_code=True)
def _(df):
    n_rows, n_cols = df.shape
    n_patients = df['patient_id'].nunique(dropna=True) if 'patient_id' in df.columns else 0
    missing_any = df.isna().any(axis=1).sum()
    missing_cells = int(df.isna().sum().sum())
    return missing_any, missing_cells, n_cols, n_patients, n_rows


@app.cell(hide_code=True)
def _(missing_any, missing_cells, mo, n_cols, n_patients, n_rows):
    mo.md(f"""
    ## Raw data overview

    This notebook evaluates the raw file index and prepares cleaned analytical datasets for downstream visit level analysis.

    ### Dataset snapshot

    - Total rows: **{n_rows:,}**
    - Total columns: **{n_cols:,}**
    - Unique patients: **{n_patients:,}**
    - Rows with at least one missing value: **{missing_any:,} ({round(missing_any / n_rows * 100, 1) if n_rows else 0}%)**
    - Total missing cells: **{missing_cells:,}**

    The workflow first audits extraction quality, then constructs cleaned document level and visit level datasets for downstream analysis.
    """)
    return


@app.cell
def _(df):
    missing_pct = (df.isnull().sum() / len(df) * 100).round(1)
    missing_pct.sort_values(ascending=False)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Audit of extraction
    This section evaluates the reliability of extracted visit dates and document types before downstream analysis.
    """)
    return


@app.cell
def _(df, pd):
    df_flagged = df.copy()

    df_flagged['visit_date_dt'] = pd.to_datetime(df['visit_date'], errors='coerce')
    df_flagged['folder_year_match'] = df_flagged['visit_date_dt'].dt.year == df_flagged['year']
    df_flagged['is_docx_date'] = df_flagged['date_source'] == 'docx'
    df_flagged['is_exact_date'] = df_flagged['date_quality'] == 'exact_anchor'
    df_flagged['is_low_confidence_date'] = df_flagged['date_quality'].isin(['fallback_single', 'fallback_scored', 'month_only'])
    df_flagged['is_unknown_type_visit'] = df_flagged['visit_type_final'] == 'unknown'
    df_flagged['is_follow_up'] = df_flagged['visit_type_final'] == 'follow_up'
    df_flagged['is_month_only'] = (df_flagged['date_rule_used'] == 'none') | (df_flagged['date_quality'] == 'month_only')

    df_flagged.head(20)
    return (df_flagged,)


@app.cell
def _(df_flagged, pd):
    pd.crosstab(df_flagged['visit_type_final'], df_flagged['date_quality'])
    return


@app.cell
def _(df_flagged, pd):
    pd.crosstab(df_flagged['year'], df_flagged['date_quality'])
    return


@app.cell
def _(df_flagged, pd):
    pd.crosstab(df_flagged['date_source'], df_flagged['date_quality'])
    return


@app.cell
def _(df_flagged, pd):
    pd.crosstab(df_flagged['visit_type'], df_flagged['visit_type_final'])
    return


@app.cell(hide_code=True)
def _(df_flagged):
    n = len(df_flagged)

    folder_year_mismatches = (~df_flagged['folder_year_match']).sum()
    raw_unknown = (df_flagged['visit_type'] == 'unknown').sum()
    final_unknown = (df_flagged['visit_type_final'] == 'unknown').sum()
    docx_dates = df_flagged['is_docx_date'].sum()
    exact_dates = df_flagged['is_exact_date'].sum()
    low_conf_dates = df_flagged['is_low_confidence_date'].sum()
    month_only = (df_flagged['date_quality'] == 'month_only').sum()
    return (
        docx_dates,
        exact_dates,
        final_unknown,
        folder_year_mismatches,
        low_conf_dates,
        month_only,
        n,
        raw_unknown,
    )


@app.cell(hide_code=True)
def _(
    docx_dates,
    exact_dates,
    final_unknown,
    folder_year_mismatches,
    low_conf_dates,
    mo,
    month_only,
    n,
    raw_unknown,
):
    mo.md(f"""
    ## Extraction audit summary

    The extraction audit was conducted on **{n:,} document level records** before any patient level processing.

    ### Key findings

    - Total records: **{n:,}**
    - Folder year mismatches: **{folder_year_mismatches:,} ({round(folder_year_mismatches / n * 100, 1) if n else 0}%)**
    - Raw unknown visit types in `visit_type`: **{raw_unknown:,} ({round(raw_unknown / n * 100, 1) if n else 0}%)**
    - Final unknown visit types in `visit_type_final`: **{final_unknown:,} ({round(final_unknown / n * 100, 1) if n else 0}%)**
    - Dates extracted from `docx`: **{docx_dates:,} ({round(docx_dates / n * 100, 1) if n else 0}%)**
    - High confidence dates with `exact_anchor`: **{exact_dates:,} ({round(exact_dates / n * 100, 1) if n else 0}%)**
    - Low confidence dates with `fallback_single`, `fallback_scored`, or `month_only`: **{low_conf_dates:,} ({round(low_conf_dates / n * 100, 1) if n else 0}%)**
    - Month only dates: **{month_only:,} ({round(month_only / n * 100, 1) if n else 0}%)**

    ### Interpretation

    Overall, extraction quality appears reasonably strong. Most records are based on `docx` sources, and a large majority of dates are classified as `exact_anchor`, which supports downstream temporal analysis.

    Document typing also improves substantially after post processing. The number of `unknown` records decreases from **{raw_unknown:,}** in the raw `visit_type` field to **{final_unknown:,}** in `visit_type_final`, which supports using `visit_type_final` as the main document type variable in later steps.
    """)
    return


@app.cell
def _(df_flagged):
    sfall_consult = df_flagged[(df_flagged['visit_type_final'] == 'consult') & (df_flagged['date_quality'] == 'fallback_single')].copy()
    sfall_consult['folder_year_match'] # only 6 of 253 MISMATCH
    sfall_consult['visit_date'].value_counts() # most of the dates are unique
    sfall_consult['is_docx_date'].value_counts() #all date source is from docx
    sfall_consult
    return


@app.cell
def _(df_flagged):
    df_flagged.to_csv('raw.csv', index = False)
    return


if __name__ == "__main__":
    app.run()
