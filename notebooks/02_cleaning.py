import marimo

__generated_with = "0.22.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import numpy as np
    import marimo as mo

    return (pd,)


@app.cell
def _(pd):
    df = pd.read_csv('../file_index_with_dates.csv')
    df.head()
    return (df,)


@app.cell
def _(df):
    df[df['visit_date'] == '2019-03-05']
    return


@app.cell
def _(df, pd):
    df['visit_date'] = pd.to_datetime(df['visit_date'])
    df['visit_date'].sort_values().value_counts() #481 rows with 2019-03-05, should check
    return


@app.cell
def _(df):
    df[df['visit_date'] == '2019-03-05']
    return


if __name__ == "__main__":
    app.run()
