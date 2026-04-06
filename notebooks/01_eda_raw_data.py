import marimo

__generated_with = "0.22.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import numpy as np
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


@app.cell
def _(df):
    df.describe()
    return


@app.cell
def _(df):
    df.isnull().sum()
    return


@app.cell
def _(df):
    missing_pct = (df.isnull().sum() / len(df) * 100).round(1)
    missing_pct
    return


@app.cell
def _(df):
    df.corr(numeric_only=True) #Most of the data is categorial, hence correlations are useless
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Data anomalies analysis

    Several extreme values and inconsistencies were manually investigated:

    - `visit_type_final = 'unknown'`: 24 rows were identified. Most of the clinical features in these entries are missing.

    - all values at 'visit_type_final' same as in 'visit_type_inferred'

    - most of the rows with `visit_type = 'unknown'` were different in 'visit_type_inferred', 7.3% of whole data.

    - `pregnancies_raw = 20` was verified against source data and found to be valid
      (sum of births, abortions, and miscarriages).

    - `births_raw = 2016` is an invalid value, likely caused by incorrect extraction
      (e.g., a year mistakenly parsed as a count).

    - `menarche_age_raw = 1` is due to a parsing error (e.g., "1 8" interpreted as 1).

    - In 80 rows, `pregnancies_raw` does not match the sum of `births_raw`,
      `abortions_raw`, and `miscarriages_raw` (excluding rows with missing values).

    - Rows with original `visit_type = 'unknown'` show a high percentage of missing
      values across clinical features.

    ### Conclusions

    - Rows where `visit_type_final = 'unknown'` contain insufficient information and
      are not suitable for analysis.

    - Not all extreme values are errors; some represent valid but rare cases.

    - Some rows contain internally inconsistent data, indicating data quality issues.

    - A significant portion of low-quality data originally labeled as `visit_type = 'unknown'`
      was reassigned to other categories (e.g., `consult`), which may bias visit-type analysis.

    - Domain knowledge and manual validation are essential for reliable preprocessing.
    """)
    return


@app.cell
def _(df):
    print((df['visit_type_final'].value_counts()['unknown'])) #number of visits, which visit type we dont know
    unknown_visit_type = df[df['visit_type_final'] == 'unknown']
    unknown_visit_type
    return


@app.cell
def _(df, pd):
    df_compare_visit_types = pd.concat([df["visit_type_final"].value_counts(), df["visit_type"].value_counts(), df["visit_type_inferred"].value_counts()],axis=1)

    df_compare_visit_types.columns = ["final", "original", "inferred"]

    df_compare_visit_types #comparing numbers of categories of visit_types features
    return


@app.cell
def _(df):
    mask_visit = df['visit_type'] == 'unknown'

    unknown_visit_missing_pct = (df[mask_visit].isna().mean() * 100).round(1) #percent of missing data(by columns) in data where original visit type was 'unknown'
    unknown_visit_missing_pct
    return


@app.cell
def _(df):
    compare_final_inferred = (df['visit_type_final'] == df['visit_type_inferred']).sum()
    compare_inferred_original = (df['visit_type_inferred'] == df['visit_type']).sum()

    compare_final_inferred
    return (compare_inferred_original,)


@app.cell
def _(compare_inferred_original, df):
    ((len(df) - compare_inferred_original) / len(df) * 100).round(1)
    return


@app.cell
def _(df):
    minimal_birth_num = df.loc[df['births_raw'].idxmax()] #probably mistake in the document, we dont know births count
    minimal_birth_num
    return


@app.cell
def _(df):
    maximal_pregnancy_number = df.loc[df['pregnancies_raw'].idxmax()] #births + abortions + miscarriages = 20, fine data
    maximal_pregnancy_number
    return


@app.cell
def _(df):
    df.loc[df['menarche_age_raw'].idxmin()] #'Менархе с 1 8 лет,' just a misstyping, replace with a 18
    return


@app.cell
def _(df, pd):
    mask = df[['pregnancies_raw','abortions_raw', 'miscarriages_raw', 'births_raw']].notna().all(axis = 1)

    misscariages_numeric = pd.to_numeric(df['miscarriages_raw'], errors="coerce")

    wrong_pregnancy_number_rows = df[(mask) & (df['pregnancies_raw'] != df['abortions_raw'] + misscariages_numeric + df['births_raw'])]
    return


if __name__ == "__main__":
    app.run()
