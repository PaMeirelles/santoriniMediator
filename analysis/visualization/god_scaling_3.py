import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
from matplotlib.patches import Patch


def analyze_god_scaling(base_path='../../data/csv'):
    """
    Loads ranking data and creates a custom grid to visualize the performance
    ranking of each God for each Engine.

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
    # 2. Prepare Data for the Custom Grid
    # -------------------------------
    print("Preparing data for the custom grid plot...")

    # Order engines by their average Elo
    sorted_engines = engine_elo_df.sort_values(by='Average Elo')['Engine'].tolist()

    # Get a list of all unique gods and create a color map
    all_gods = sorted(ranking_df['God'].unique())
    palette = sns.color_palette("husl", len(all_gods))
    god_color_map = dict(zip(all_gods, palette))

    # -------------------------------
    # 3. Generate the Custom Grid Plot
    # -------------------------------
    print("Generating the custom grid plot...")

    num_gods = len(all_gods)
    num_engines = len(sorted_engines)

    fig, ax = plt.subplots(figsize=(max(20, 1.5 * num_engines), 10))
    ax.set_xlim(-0.5, num_engines - 0.5)
    ax.set_ylim(-0.5, num_gods - 0.5)
    ax.invert_yaxis()  # Rank 1 at the top

    # Iterate through each engine to draw its column
    for engine_idx, engine_name in enumerate(sorted_engines):
        # Get data for the current engine and sort gods by Elo for ranking
        engine_data = ranking_df[ranking_df['Engine'] == engine_name].sort_values(by='Elo', ascending=False)

        # Draw a cell for each god based on its rank for this engine
        for god_rank, (_, row) in enumerate(engine_data.iterrows()):
            god_name = row['God']
            god_elo = row['Elo']
            color = god_color_map[god_name]

            # Draw the colored cell
            rect = plt.Rectangle((engine_idx - 0.5, god_rank - 0.5), 1, 1,
                                 facecolor=color, edgecolor='black', linewidth=0.5, alpha=0.8)
            ax.add_patch(rect)

            # Add text inside the cell (God name and Elo)
            text_color = 'white' if sum(color[:3]) < 1.5 else 'black'
            ax.text(engine_idx, god_rank, f"{god_name}\n{god_elo:.0f}",
                    ha='center', va='center', fontsize=9, color=text_color, weight='bold')

    # -------------------------------
    # 4. Customize and Save
    # -------------------------------
    ax.set_title('God Performance Ranking per Engine', fontsize=20, pad=20)
    ax.set_xlabel('Engine (Ordered by Strength)', fontsize=14)
    ax.set_ylabel('Performance Rank', fontsize=14)

    # Set x-axis labels to engine names
    ax.set_xticks(range(num_engines))
    ax.set_xticklabels(sorted_engines, rotation=45, ha='right')

    # Set y-axis labels to ranks
    ax.set_yticks(range(num_gods))
    ax.set_yticklabels([f'Rank {i + 1}' for i in range(num_gods)])

    # Create a custom legend for the god colors
    legend_elements = [Patch(facecolor=god_color_map[god], edgecolor='black', label=god)
                       for god in all_gods]
    ax.legend(handles=legend_elements, bbox_to_anchor=(1.02, 1), loc='upper left', title="Gods")

    # Adjust layout to prevent legend from being cut off
    plt.tight_layout(rect=[0, 0, 0.9, 1])

    output_filename = 'god_engine_ranking_grid.png'
    plt.savefig(output_filename, dpi=150, bbox_inches='tight')

    print(f"\n✅ Plot successfully saved as '{output_filename}'")
    plt.show()


if __name__ == '__main__':
    analyze_god_scaling(base_path='../../data')

