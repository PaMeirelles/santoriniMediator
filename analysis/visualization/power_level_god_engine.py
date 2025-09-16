import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os


def analyze_god_scaling(rankings_file='../../data/god_engine_rankings.csv', engines_file='../../data/engine_average_elo.csv'):
    """
    Loads ranking data, merges it, and creates a plot to visualize
    how god strength scales with engine strength.

    Args:
        rankings_file (str): Path to the CSV file with God-Engine pair rankings.
        engines_file (str): Path to the CSV file with average engine Elo.
    """
    # -------------------------------
    # 1. Validate and Load Data
    # -------------------------------
    if not os.path.exists(rankings_file) or not os.path.exists(engines_file):
        print(f"Error: Make sure both '{rankings_file}' and '{engines_file}' are in the same directory as this script.")
        print("Please run the first script to generate these files.")
        return

    print(f"Loading data from '{rankings_file}' and '{engines_file}'...")
    try:
        # Load the detailed rankings for each God-Engine pair
        ranking_df = pd.read_csv(rankings_file)

        # Load the average Elo for each engine
        engine_elo_df = pd.read_csv(engines_file)

        # Ensure Elo columns are numeric for plotting
        ranking_df['Elo'] = pd.to_numeric(ranking_df['Elo'], errors='coerce')
        engine_elo_df['Average Elo'] = pd.to_numeric(engine_elo_df['Average Elo'], errors='coerce')

        # Drop any rows that couldn't be converted to numbers
        ranking_df.dropna(subset=['Elo'], inplace=True)
        engine_elo_df.dropna(subset=['Average Elo'], inplace=True)

    except Exception as e:
        print(f"An error occurred while reading the CSV files: {e}")
        return

    # -------------------------------
    # 2. Merge DataFrames
    # -------------------------------
    # Combine the two dataframes to link each pair's Elo with the engine's average Elo.
    # This gives us a single table with engine strength (Average Elo) and pair performance (Elo).
    print("Merging dataframes to link engine strength with pair performance...")
    merged_df = pd.merge(ranking_df, engine_elo_df, on='Engine')

    if merged_df.empty:
        print("The merged dataframe is empty. Please check the contents of your CSV files.")
        return

    # -------------------------------
    # 3. Generate the Plot
    # -------------------------------
    print("Generating the plot...")

    # Set a professional plot style
    sns.set_theme(style="whitegrid")

    # Use seaborn's lmplot to create a scatter plot with a regression line for each god.
    # 'hue' separates the data by 'God', giving each a unique color and trend line.
    # 'ci=None' disables the confidence interval bands to keep the plot clean.
    g = sns.lmplot(
        data=merged_df,
        x='Average Elo',  # Engine strength
        y='Elo',  # Performance of the God-Engine pair
        hue='God',  # Color points by god
        height=8,  # Make the plot taller
        aspect=1.5,  # Make the plot wider
        ci=None,  # Turn off confidence intervals for clarity
        scatter_kws={'alpha': 0.7}  # Make points slightly transparent
    )

    # -------------------------------
    # 4. Customize and Save
    # -------------------------------
    # Set titles and labels for clarity
    g.fig.suptitle('God Performance vs. Engine Strength', fontsize=18, y=1.02)
    g.set_axis_labels('Engine Average Elo (Engine Strength)', 'God-Engine Pair Elo (Performance)', fontsize=12)
    g.ax.set_title("Each point is a God-Engine pair. Lines show the trend for each god.", fontsize=12, pad=15)

    # Save the plot to a file
    output_filename = 'god_performance_vs_engine_elo.png'
    plt.savefig(output_filename, bbox_inches='tight', dpi=150)

    print(f"\n✅ Plot successfully saved as '{output_filename}'")

    # Display the plot
    plt.show()


if __name__ == '__main__':
    analyze_god_scaling()
