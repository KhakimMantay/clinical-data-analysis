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
    df
    return (df,)


@app.cell
def _(df):
    ANALYSIS_PERIOD_START = 2021
    df['dataset_flag'] = df['visit_day'].dt.year.map(lambda y: '2021_plus' if y >= ANALYSIS_PERIOD_START else '2019-2020')

    df[df['visit_day'].dt.year >= ANALYSIS_PERIOD_START]['dataset_flag'].value_counts()
    return (ANALYSIS_PERIOD_START,)


@app.cell
def _(ANALYSIS_PERIOD_START, df, pd):
    def summarize_visits(data, label):
        out = {
            'dataset': label,
            'n_visits': len(data),
            'n_unique_patients': data['patient_id'].nunique(),
            'visits_per_patient': round(len(data) / data['patient_id'].nunique(), 2),
            'mean_age_at_visit': data['age_at_visit_approx'].mean().round(1),
            'median_age_at_visit': data['age_at_visit_approx'].median(),
            'ultrasound_share_pct': (data['has_ultrasound'].mean() * 100).round(1),
            'mean_global_visit_number': data['visit_number'].mean().round(2),
            'median_global_visit_number': data['visit_number'].median(),
            'prev_visit_interval_available_pct': (data['days_since_prev_visit'].notna().mean() * 100).round(1),
            'mean_days_since_prev_visit': data['days_since_prev_visit'].dropna().mean().round(1),
            'median_days_since_prev_visit': data['days_since_prev_visit'].dropna().median(),
            'mean_n_docs_in_visit': data['n_docs_in_visit'].mean().round(2),
            'median_n_docs_in_visit': data['n_docs_in_visit'].median(),
            'primary_visit_type_pct' : (data['visit_type_grouped'] == 'primary').mean().round(2),
            'ultrasound_visit_type_pct' : (data['visit_type_grouped'] == 'ultrasound').mean().round(2)
        }

        return out

    all_years_df = df.copy()
    analysis_df = df[df['dataset_flag'] == '2021_plus'].copy()

    period_comparison = pd.DataFrame([
        summarize_visits(all_years_df, 'all_years'), 
        summarize_visits(analysis_df, f'{ANALYSIS_PERIOD_START}_plus')
    ])

    period_comparison
    return analysis_df, summarize_visits


@app.cell
def _(df, pd):
    visit_type_comparison = (pd.crosstab(df['dataset_flag'], df['visit_type_grouped'], normalize='index') * 100).round(1)
    visit_type_comparison
    return


@app.cell
def _(df):
    mask = df['dataset_flag'].eq('2019-2020')
    df['has_history_before_2021'] = mask.groupby(df['patient_id']).transform('any')

    df
    return


@app.cell
def _(df):
    dataset_mask = df['dataset_flag'] == '2021_plus'

    new_patients_visits_df = df[dataset_mask & ~df['has_history_before_2021']]
    old_patients_visits_df = df[dataset_mask & df['has_history_before_2021']]

    new_patients_visits_df
    return new_patients_visits_df, old_patients_visits_df


@app.cell
def _(old_patients_visits_df):
    old_patients_visits_df
    return


@app.cell
def _(new_patients_visits_df, old_patients_visits_df, pd, summarize_visits):
    patient_comparison = pd.DataFrame([
        summarize_visits(new_patients_visits_df, 'new_2021_plus_patients'), 
        summarize_visits(old_patients_visits_df, 'old_2021_plus_patients')
    ])

    patient_comparison
    return


@app.cell
def _(analysis_df, new_patients_visits_df, pd, summarize_visits):
    patient_groups_comparison = pd.DataFrame([
        summarize_visits(new_patients_visits_df, 'new_2021_plus_patients'), 
        summarize_visits(analysis_df, 'all_2021_plus_patients')
    ])

    patient_groups_comparison
    return


@app.cell
def _(analysis_df, pd, summarize_visits):
    target_group_summary = pd.Series(summarize_visits(analysis_df, 'all_2021_plus_patients'))

    target_group_summary
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
