import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
from scipy.stats import linregress


def analyze_god_scaling(base_path='../../data/csv'):
    """
    Loads ranking data, calculates the performance scaling factor (slope) for each god,
    and creates a bar chart to visualize how god strength scales with engine strength.

    Args:
        base_path (str): The base directory where the CSV files are located.
    """
    # -------------------------------
    # 1. Validate and Load Data
    # -------------------------------
    rankings_file = os.path.join(base_path, 'god_engine_rankings.csv')
    engines_file = os.path.join(base_path, 'engine_average_elo.csv')

    if not os.path.exists(rankings_file) or not os.path.exists(engines_file):
        print(
            f"Error: Make sure both '{os.path.basename(rankings_file)}' and '{os.path.basename(engines_file)}' exist in the '{base_path}' directory.")
        print("Please run the first script to generate these files.")
        return

    print(f"Loading data from '{rankings_file}' and '{engines_file}'...")
    try:
        ranking_df = pd.read_csv(rankings_file)
        engine_elo_df = pd.read_csv(engines_file)

        ranking_df['Elo'] = pd.to_numeric(ranking_df['Elo'], errors='coerce')
        engine_elo_df['Average Elo'] = pd.to_numeric(engine_elo_df['Average Elo'], errors='coerce')

        ranking_df.dropna(subset=['Elo'], inplace=True)
        engine_elo_df.dropna(subset=['Average Elo'], inplace=True)
    except Exception as e:
        print(f"An error occurred while reading the CSV files: {e}")
        return

    # -------------------------------
    # 2. Merge DataFrames
    # -------------------------------
    print("Merging dataframes...")
    merged_df = pd.merge(ranking_df, engine_elo_df, on='Engine')

    if merged_df.empty:
        print("The merged dataframe is empty. Please check the contents of your CSV files.")
        return

    # -------------------------------
    # 3. Calculate Performance Slope for Each God
    # -------------------------------
    print("Calculating performance scaling factor for each god...")
    god_slopes = []

    for god in merged_df['God'].unique():
        god_df = merged_df[merged_df['God'] == god]
        # Need at least two points to determine a line
        if len(god_df) >= 2:
            # linregress returns: slope, intercept, r_value, p_value, std_err
            slope, _, _, _, _ = linregress(god_df['Average Elo'], god_df['Elo'])
            god_slopes.append({'God': god, 'Scaling Factor': slope})

    if not god_slopes:
        print("Could not calculate slopes. Please ensure there is enough data for each god.")
        return

    slope_df = pd.DataFrame(god_slopes).sort_values(by='Scaling Factor', ascending=False)

    # -------------------------------
    # 4. Generate the New Plot (Bar Chart)
    # -------------------------------
    print("Generating the bar chart...")

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    # Create the bar plot
    sns.barplot(
        data=slope_df,
        x='Scaling Factor',
        y='God',
        palette='viridis',
        ax=ax
    )

    # Add text labels to the bars
    for container in ax.containers:
        ax.bar_label(container, fmt='%.3f', padding=3, fontsize=10)

    # -------------------------------
    # 5. Customize and Save
    # -------------------------------
    ax.set_title('God Performance Scaling vs. Engine Strength', fontsize=18, pad=20)
    ax.set_xlabel('Performance Scaling Factor (Elo Gain per Engine Elo Point)', fontsize=12)
    ax.set_ylabel('God', fontsize=12)

    # Adjust x-axis limits for padding
    ax.set_xlim(right=ax.get_xlim()[1] * 1.1)

    plt.tight_layout()

    output_filename = 'god_performance_scaling_barchart.png'
    plt.savefig(output_filename, dpi=150)

    print(f"\n✅ Plot successfully saved as '{output_filename}'")

    plt.show()


if __name__ == '__main__':
    # You can change the path here if your data is in a different location
    analyze_god_scaling(base_path='../../data')

