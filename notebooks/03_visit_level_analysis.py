import marimo

__generated_with = "0.22.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    return (pd,)


@app.cell
def _(pd):
    df = pd.read_csv('visits.csv', parse_dates = ['visit_day'])

    df.head()
    return (df,)


@app.cell
def _(df):
    df['analysis_period'] = df['visit_day'].dt.year.map(lambda y: '2019_2020' if y < 2021 else '2021_plus')
    return


@app.cell
def _(df):
    period_summary = (
        df.groupby('analysis_period').agg(
            n_visits = ('patient_id', 'size'),
            patients_unique = ('patient_id', 'nunique'),
            ultrasound_share = ('has_ultrasound', 'mean'),
            median_days_since_prev_visit = ('days_since_prev_visit', 'median'),
            mean_days_since_prev_visit = ('days_since_prev_visit', 'mean'),
            median_n_docs_in_visit = ('n_docs_in_visit', 'median'),
            mean_n_docs_in_visit = ('n_docs_in_visit', 'mean')
        ).reset_index()
    )

    period_summary
    return


@app.cell
def _(df):
    df.info()
    return


@app.cell
def _(df):
    len(df)
    return


@app.cell
def _(df):
    df['patient_id'].nunique()
    return


@app.cell
def _(df):
    (df['visit_number'].value_counts() / len(df) * 100).round(2)
    return


@app.cell
def _(df):
    (df['has_ultrasound'].value_counts() / len(df) * 100).round(2)
    return


@app.cell
def _(df):
    (df['visit_type'].value_counts() / len(df) * 100).round(2)
    return


@app.cell
def _(df):
    (df['visit_type_grouped'].value_counts() / len(df) * 100).round(2)
    return


@app.cell
def _(df):
    df['days_since_prev_visit'].dropna().describe()
    return


@app.cell
def _(df):
    df[df['patient_id'] == df.loc[df['days_since_prev_visit'].idxmax()]['patient_id']] #fine data
    return


@app.cell
def _(df):
    df['n_docs_in_visit'].describe()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
