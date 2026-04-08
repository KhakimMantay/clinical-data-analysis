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
    raw_df = pd.read_csv('../file_index_with_dates.csv')
    raw_df.head()
    return (raw_df,)


@app.cell
def _(pd, raw_df):
    typed_df = raw_df.assign(visit_date = pd.to_datetime(raw_df['visit_date']))
    typed_df.head()
    return (typed_df,)


@app.cell
def _(typed_df):
    clean_vtype_df = typed_df[(typed_df['visit_type'] != 'unknown')].copy()
    clean_vtype_df = clean_vtype_df[clean_vtype_df['date_source'] != 'mtime']
    print(clean_vtype_df[clean_vtype_df['date_source'] == 'path']['year'].value_counts().sort_index())
    return (clean_vtype_df,)


@app.cell
def _(clean_vtype_df):
    without_extreme_df = clean_vtype_df[(clean_vtype_df['births_raw'] != 2016) & (clean_vtype_df['menarche_age_raw'] != 1)]
    without_extreme_df[(without_extreme_df['births_raw'] == 2016) | (without_extreme_df['menarche_age_raw'] == 1)]
    return (without_extreme_df,)


@app.cell
def _(without_extreme_df):
    reduced_df = without_extreme_df.drop(columns = ['category' ,'month', 'year', 'date_rule_used', 'date_candidates_count', 'date_source', 'fio_source', 'size_bytes', 'mtime', 'visit_type_inferred', 'visit_type_final'])
    return (reduced_df,)


@app.cell
def _(reduced_df):
    clean_bday_df = reduced_df[reduced_df['birth_year'].notna()]
    clean_bday_df['birth_year'] = clean_bday_df['birth_year'].astype(int)
    clean_bday_df.head()
    return (clean_bday_df,)


@app.cell
def _(clean_bday_df):
    clean_bday_df['date_exact'] = True

    clean_bday_df.loc[
        clean_bday_df["date_quality"].isin(["fallback_single", "month_only"]), "date_exact"] = False

    flagged_df = clean_bday_df.drop(columns = 'date_quality')
    flagged_df
    return (flagged_df,)


@app.cell
def _(flagged_df):
    flagged_df['age_at_visit_approx'] = flagged_df['visit_date'].dt.year - flagged_df['birth_year']
    age_df = flagged_df.drop(columns = 'birth_year')
    age_df
    return (age_df,)


@app.cell
def _(age_df, pd):
    visit_count_df = age_df.sort_values(['patient_id', 'visit_date']).drop_duplicates(['patient_id', 'visit_date']).copy()
    visit_count_df['visit_number'] = visit_count_df.groupby('patient_id').cumcount() + 1
    visit_count_df = visit_count_df[['patient_id', 'visit_date', 'visit_number']]

    retention_df = age_df.sort_values(['patient_id', 'visit_date']).copy()
    retention_df = pd.merge(retention_df, visit_count_df, on = ['patient_id', 'visit_date'], how = 'left')

    retention_df
    return (retention_df,)


@app.cell
def _(pd, retention_df):
    prev_visit_df = retention_df.sort_values(['patient_id', 'visit_date']).drop_duplicates(['patient_id', 'visit_date']).copy()

    prev_visit_df['days_since_prev_visit'] = (prev_visit_df['visit_date'] - prev_visit_df.groupby('patient_id')['visit_date'].shift(1)).dt.days
    prev_visit_df

    prev_visit_df = pd.merge(retention_df,
        prev_visit_df[['patient_id', 'visit_date', 'days_since_prev_visit']],
        on = ['patient_id', 'visit_date'],
        how = 'left')

    prev_visit_df
    return (prev_visit_df,)


@app.cell
def _(prev_visit_df):
    weekday_df = prev_visit_df.copy()
    weekday_df['weekday'] = weekday_df['visit_date'].dt.day_name()
    weekday_df['weekday_num'] = weekday_df['visit_date'].dt.weekday

    weekday_df
    return (weekday_df,)


@app.cell
def _(weekday_df):
    clean_df = weekday_df.copy()
    clean_df.to_csv('clean.csv')
    return


if __name__ == "__main__":
    app.run()
