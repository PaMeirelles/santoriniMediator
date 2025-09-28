import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from analysis.visualization.visualization import get_conn


def analyze_god_scaling():
    """
    Loads ranking data from the database and creates a custom grid to visualize the performance
    ranking of each God for each Engine.
    """
    # -------------------------------
    # 1. Load Data from Database
    # -------------------------------
    print("Connecting to the database to load Elo data...")
    conn = get_conn()
    try:
        # Query for individual God-Engine Elo ratings
        ranking_query = "SELECT God, Engine, Elo FROM TB_ELO"
        ranking_df = pd.read_sql_query(ranking_query, conn)

        # Query for the average Elo per engine to determine engine strength
        engine_elo_query = """
            SELECT Engine, AVG(Elo) AS "Average Elo"
            FROM TB_ELO
            GROUP BY Engine
        """
        engine_elo_df = pd.read_sql_query(engine_elo_query, conn)

        print(f"Successfully loaded {len(ranking_df)} God-Engine records and {len(engine_elo_df)} engine averages.")

        # Data validation and type conversion
        ranking_df['Elo'] = pd.to_numeric(ranking_df['Elo'], errors='coerce')
        engine_elo_df['Average Elo'] = pd.to_numeric(engine_elo_df['Average Elo'], errors='coerce')

        ranking_df.dropna(subset=['Elo'], inplace=True)
        engine_elo_df.dropna(subset=['Average Elo'], inplace=True)

    except Exception as e:
        print(f"❌ An error occurred while querying the database: {e}")
        return
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

    if ranking_df.empty or engine_elo_df.empty:
        print("Error: No data was loaded from the database. Cannot generate plot.")
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
            color = god_color_map.get(god_name) # Use .get for safety

            if color is None: continue # Skip if god somehow not in map

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
    # Make sure we don't have more ticks than available ranks
    max_rank = ranking_df.groupby('Engine')['God'].nunique().max()
    ax.set_yticks(range(max_rank))
    ax.set_yticklabels([f'Rank {i + 1}' for i in range(max_rank)])
    ax.set_ylim(max_rank - 0.5, -0.5) # Adjust y-lim to fit the max rank


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
    analyze_god_scaling()