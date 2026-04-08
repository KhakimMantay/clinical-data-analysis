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

    - All values in `visit_type_final` are identical to those in `visit_type_inferred`.

    - Most of the rows with original `visit_type = 'unknown'` were reassigned in `visit_type_inferred` (~7.3% of the dataset).

    - `pregnancies_raw = 20` was verified against source data and found to be valid
      (sum of births, abortions, and miscarriages).

    - `births_raw = 2016` is an invalid value, likely caused by incorrect extraction
      (e.g., a year mistakenly parsed as a count).

    - `menarche_age_raw = 1` is an error

    - In 80 rows, `pregnancies_raw` does not match the sum of `births_raw`,
      `abortions_raw`, and `miscarriages_raw` (excluding rows with missing values).

    - Rows with original `visit_type = 'unknown'` show a high percentage of missing
      values across clinical features.

    - Multiple records can correspond to a single real-world visit, as different document types
      (e.g., ultrasound, consultation) may be created for the same patient on the same date.

    - Some visit dates were inferred as the first day of the month (`YYYY-MM-01`) due to missing
      day information (`date_quality = 'month_only'`), which introduces artificial spikes in daily counts.

    - High-frequency dates (e.g., 30+ records per day) were found to consist of both valid extracted
      dates (`exact_anchor`) and imputed dates (`month_only`), indicating mixed data quality.

    ---

    ### Conclusions and required data cleaning steps

    The exploratory data analysis revealed several data quality issues that must be addressed before further analysis:

    - Rows where `visit_type_final = 'unknown'` contain insufficient information and should be removed, as they provide little analytical value and contain a high proportion of missing features.

    - Some clinical variables contain clear extraction errors (e.g., unrealistic values such as `births_raw = 2016` or `menarche_age_raw = 1`). These values must be cleaned, corrected, or excluded to prevent distortion of statistical analysis.

    - Internal inconsistencies were identified (e.g., `pregnancies_raw` not matching the sum of related variables). These rows should be validated or excluded depending on the analysis requirements.

    - Visit dates with `date_quality = 'month_only'` are artificially imputed and lead to biased temporal distributions (e.g., spikes on the first day of each month). These rows should be excluded or handled separately in time-based analyses.

    - The dataset is structured at the file level rather than the visit level, meaning that multiple rows may correspond to a single real-world visit. Therefore, aggregation by `(patient_id, visit_date)` is required to correctly represent visits.

    - The presence of fallback-based date extraction (e.g., `fallback_single`, `fallback_scored`) indicates that the date extraction logic may be incomplete, particularly for certain document types (e.g., ultrasound). Further refinement of the extraction pipeline is recommended.

    - High-frequency dates must be interpreted with caution, as they may reflect a mixture of true visit dates and imputed or low-confidence values.

    Overall, additional preprocessing is required to ensure data reliability before performing statistical analysis or building models.
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
    mask_suspicious = (df['visit_type'] == 'unknown') & (df['visit_type_final'] != 'unknown')

    key_cols = ['visit_date', 'birth_year', 'complaints_raw', 
                'diagnosis_raw', 'birads_raw']

    (df[mask_suspicious][key_cols].isnull().mean() * 100).round(1)
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
    wrong_pregnancy_number_rows
    return


@app.cell
def _(df):
    df[['date_rule_used', 'date_quality']].value_counts()
    return


@app.cell
def _(df):
    df[df['date_rule_used'] == 'fallback_single'].head(10)
    return


@app.cell
def _(df):
    ultrasound_date_rule = (df[df['visit_type_inferred'] == 'ultrasound']['date_rule_used'] == 'fallback_single')
    ultrasound_date_rule.value_counts()
    return


@app.cell
def _(df):
    df[(df['visit_type_final'] == 'ultrasound') & (df['date_rule_used'] != 'fallback_single')]
    return


@app.cell
def _(df):
    df[df['date_rule_used'] == 'none'][['visit_date', 'date_quality']]
    return


@app.cell
def _(df):
    df['visit_date'].value_counts() # too many visits on some dates, should check
    return


@app.cell
def _(df):
    df['visit_date'].value_counts().head()
    return


@app.cell
def _(df):
    visits = df.drop_duplicates(subset=['patient_id', 'visit_date'])
    visits['visit_date'].value_counts().head()
    return


@app.cell
def _(df):
    df[df['visit_date'] == '2020-03-01']['date_quality'].value_counts()
    return


@app.cell
def _(df):
    df['date_quality'].value_counts()
    return


@app.cell
def _(df):
    df['date_source'].value_counts()
    return


if __name__ == "__main__":
    app.run()
