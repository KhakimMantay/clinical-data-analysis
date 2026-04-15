import marimo

__generated_with = "0.22.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import marimo as mo

    return (pd,)


@app.cell
def _(pd):
    raw_df = pd.read_csv('raw.csv', parse_dates = ['visit_date_dt'])
    raw_df.head()
    return (raw_df,)


@app.cell
def _(raw_df):
    raw_df.columns
    return


@app.cell
def _(raw_df):
    clean_df = raw_df.dropna(subset = ['patient_id', 'visit_date', 'visit_date_dt']).copy()

    clean_df = clean_df[clean_df['date_source'] != 'mtime'].copy()
    clean_df = clean_df[~clean_df['visit_type_final'].isin(['template', 'unknown'])].copy()

    clean_df["visit_type_grouped"] = clean_df["visit_type_final"].replace({
        "follow_up": "primary",
        "consult": "primary",
        "ultrasound_onco": "ultrasound"})

    clean_df = clean_df.drop(columns = ['category', 'month', 'size_bytes', 'mtime', 'fio_source', 'date_candidates_count', 'visit_type_inferred', 'is_unknown_type_visit', 'visit_date', 'date_rule_used', 'visit_type'])

    clean_df = clean_df.rename(columns={'visit_date_dt': 'visit_datetime', 'visit_type_final' : 'visit_type'})

    clean_df['age_at_visit_approx'] = clean_df['visit_datetime'].dt.year - clean_df['birth_year']

    clean_df
    return (clean_df,)


@app.cell
def _(clean_df, pd):
    type_mapping_check = pd.crosstab(
            clean_df['visit_type'],
            clean_df['visit_type_grouped'],
            margins=True
        )
    type_mapping_check
    return


@app.cell
def _(clean_df):
    strict_df = clean_df.copy()

    strict_df = strict_df[strict_df['folder_year_match'] & strict_df['is_docx_date'] & strict_df['is_exact_date']].copy()

    strict_df =  strict_df.drop(columns = ['year', 'folder_year_match', 'is_docx_date', 'is_exact_date', 'is_low_confidence_date', 'is_follow_up', 'is_month_only', 'date_quality'])

    strict_df
    return (strict_df,)


@app.cell
def _(strict_df):
    visit_level_df = strict_df.copy()
    visit_level_df["visit_day"] = visit_level_df["visit_datetime"].dt.normalize()

    visit_level_df['has_ultrasound'] = visit_level_df.groupby(['patient_id', 'visit_day'])['visit_type_grouped'].transform(lambda s: (s == 'ultrasound').any())
    visit_level_df['n_docs_in_visit'] = visit_level_df.groupby(['patient_id', 'visit_day'])['visit_type_grouped'].transform('size')

    visit_level_df['visit_type_priority'] = visit_level_df['visit_type_grouped'].map({'primary' : 0, 'ultrasound' : 1}).fillna(99)
    visit_level_df = visit_level_df.sort_values(['patient_id', 'visit_day', 'visit_type_priority']).drop_duplicates(['patient_id', 'visit_day']).copy()

    visit_level_df['visit_number'] = visit_level_df.groupby('patient_id').cumcount() + 1
    visit_level_df['days_since_prev_visit'] = (visit_level_df['visit_day'] - visit_level_df.groupby('patient_id')['visit_day'].shift(1)).dt.days

    visit_level_df = visit_level_df[['patient_id', 'birth_year', 'age_at_visit_approx', 'visit_type','visit_type_grouped', 'visit_day', 'visit_number', 'days_since_prev_visit', 'has_ultrasound', 'n_docs_in_visit']].copy()

    visit_level_df
    return (visit_level_df,)


@app.cell
def _(clean_df, pd, raw_df, strict_df, visit_level_df):
    def stage_metrics(df, stage_name, visit_day_col=None):
            out = {
                'stage': stage_name,
                'n_rows': len(df),
                'n_patients': df['patient_id'].nunique()
            }

            if visit_day_col is None:
                out['n_patient_days'] = pd.NA
            else:
                out['n_patient_days'] = (
                    df[['patient_id', visit_day_col]]
                    .drop_duplicates()
                    .shape[0]
                )

            return out

    retention_summary = pd.DataFrame([
        stage_metrics(raw_df, 'raw_df'),
        stage_metrics(clean_df, 'clean_df'),
        stage_metrics(strict_df, 'strict_df', visit_day_col='visit_datetime'),
        stage_metrics(visit_level_df, 'visit_level_df', visit_day_col='visit_day'),
    ])

    retention_summary['rows_retained_vs_raw_pct'] = (
        retention_summary['n_rows'] / retention_summary.loc[0, 'n_rows'] * 100
    ).round(1)

    retention_summary['patients_retained_vs_raw_pct'] = (
        retention_summary['n_patients'] / retention_summary.loc[0, 'n_patients'] * 100
    ).round(1)

    retention_summary
    return


@app.cell
def _(clean_df, strict_df):
    strict_keys = strict_df[['patient_id', 'visit_datetime', 'visit_type']].drop_duplicates().copy()

    clean_with_flag = clean_df.merge(
        strict_keys.assign(is_retained_in_strict=True),
        on=['patient_id', 'visit_datetime', 'visit_type'],
        how='left'
    )

    clean_with_flag['is_retained_in_strict'] = clean_with_flag['is_retained_in_strict'].fillna(False)

    loss_by_doc_type = (
        clean_with_flag
        .groupby('visit_type', dropna=False)['is_retained_in_strict']
        .agg(
            n_total='size',
            n_retained='sum'
        )
        .reset_index()
    )

    loss_by_doc_type['n_lost'] = loss_by_doc_type['n_total'] - loss_by_doc_type['n_retained']
    loss_by_doc_type['retained_pct'] = (loss_by_doc_type['n_retained'] / loss_by_doc_type['n_total'] * 100).round(1)
    loss_by_doc_type = loss_by_doc_type.sort_values(['retained_pct', 'n_total'])

    loss_by_doc_type
    return (clean_with_flag,)


@app.cell
def _(clean_with_flag):
    loss_by_year = (
        clean_with_flag
        .groupby('year', dropna=False)['is_retained_in_strict']
        .agg(
            n_total='size',
            n_retained='sum'
        )
        .reset_index()
    )

    loss_by_year['n_lost'] = loss_by_year['n_total'] - loss_by_year['n_retained']
    loss_by_year['retained_pct'] = (loss_by_year['n_retained'] / loss_by_year['n_total'] * 100).round(1)

    loss_by_year
    return


@app.cell
def _(clean_df):
    strict_failure_flags = clean_df.copy()

    strict_failure_flags['fails_folder_year_match'] = ~strict_failure_flags['folder_year_match']
    strict_failure_flags['fails_docx_date'] = ~strict_failure_flags['is_docx_date']
    strict_failure_flags['fails_exact_date'] = ~strict_failure_flags['is_exact_date']

    strict_failure_flags['n_failed_rules'] = strict_failure_flags[
        ['fails_folder_year_match', 'fails_docx_date', 'fails_exact_date']
    ].sum(axis=1)

    strict_failure_flags[['fails_folder_year_match', 'fails_docx_date', 'fails_exact_date', 'n_failed_rules']].sum()
    return (strict_failure_flags,)


@app.cell
def _(strict_failure_flags):
    failure_pattern_summary = (
        strict_failure_flags
        .groupby([
            'fails_folder_year_match',
            'fails_docx_date',
            'fails_exact_date'
        ])
        .size()
        .reset_index(name='n_rows')
        .sort_values('n_rows', ascending=False)
    )

    failure_pattern_summary
    return


@app.cell
def _(strict_failure_flags):
    consult_failure_breakdown = (
        strict_failure_flags[strict_failure_flags['visit_type'] == 'consult']
        .groupby(['fails_folder_year_match', 'fails_docx_date', 'fails_exact_date'])
        .size()
        .reset_index(name='n_rows')
        .sort_values('n_rows', ascending=False)
    )

    consult_failure_breakdown
    return


@app.cell
def _(strict_failure_flags):
    failure_by_type = (
        strict_failure_flags
        .groupby('visit_type')[['fails_folder_year_match', 'fails_docx_date', 'fails_exact_date']]
        .mean()
        .round(3)
        .sort_values('fails_exact_date', ascending=False)
    )

    failure_by_type
    return


@app.cell
def _(clean_with_flag):
    patient_retention = (
        clean_with_flag
        .groupby('patient_id')['is_retained_in_strict']
        .agg(
            n_docs_total='size',
            n_docs_retained='sum'
        )
        .reset_index()
    )

    patient_retention['all_docs_lost'] = patient_retention['n_docs_retained'] == 0
    patient_retention['partially_lost'] = (
        (patient_retention['n_docs_retained'] > 0)
        & (patient_retention['n_docs_retained'] < patient_retention['n_docs_total'])
    )

    patient_retention[['all_docs_lost', 'partially_lost']].sum()
    return


@app.cell
def _(clean_df, strict_df, visit_level_df):
    clean_df.to_csv('clean.csv', index = False)
    strict_df.to_csv('strict.csv', index = False)
    visit_level_df.to_csv('visits.csv', index = False)
    return


if __name__ == "__main__":
    app.run()
