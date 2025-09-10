import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re
from typing import Tuple

# --- CONFIGURATION ---
DB_FILE_PATH = r"/data/matches.db"
OUTPUT_DIR = "../results/analysis_results"

# --- ENGINE COMPARISON CONFIGURATION ---
# Set the names of the two engines you want to compare.
# The script will validate these names against the engines found in the database.
ENGINE_1 = "Paladini_5.0_Velocity"
ENGINE_2 = "Paladini_5.5.11_Velocity"


# --- God Mapping ---
# Maps the integer ID from the position string to the God's name
GOD_MAP = {
    0: "APOLLO", 1: "ARTEMIS", 2: "ATHENA", 3: "ATLAS", 4: "DEMETER",
    5: "HEPHAESTUS", 6: "HERMES", 7: "MINOTAUR", 8: "PAN", 9: "PROMETHEUS",
}


def extract_gods_from_position(position_str: str) -> Tuple[str, str]:
    """Extracts god IDs from the FEN-like position string."""
    return position_str[-3], position_str[-2]


def compare_engines_per_depth(df: pd.DataFrame, engine1_name: str, engine2_name: str, depth: int):
    """
    Compares two engines on move equality, nodes, time, and score for a specific depth.
    """
    print(f"\n--- Comparing Engines at Depth {depth}: {engine1_name} vs. {engine2_name} ---")

    # Filter by the specific depth
    depth_df = df[df['depth'] == depth]

    # Filter the DataFrame for each engine
    df_engine1 = depth_df[depth_df['engine'] == engine1_name].copy()
    df_engine2 = depth_df[depth_df['engine'] == engine2_name].copy()

    if df_engine1.empty or df_engine2.empty:
        print(f"Data for one or both engines is missing at depth {depth}.")
        return

    # Merge the dataframes on the 'position' column to align the data for comparison
    merged_df = pd.merge(df_engine1, df_engine2, on='position', suffixes=(f'_{engine1_name}', f'_{engine2_name}'))

    if merged_df.empty:
        print(f"No common positions found between the two engines to compare at depth {depth}.")
        return

    # --- Percentage of Equal Moves ---
    equal_moves = (merged_df[f'move_{engine1_name}'] == merged_df[f'move_{engine2_name}']).sum()
    total_moves = len(merged_df)
    percentage_equal_moves = (equal_moves / total_moves) * 100
    print(f"Percentage of Equal Moves: {percentage_equal_moves:.2f}%")

    # --- Nodes and Time Searched Comparison ---
    avg_nodes_engine1 = merged_df[f'nodes_{engine1_name}'].mean()
    avg_nodes_engine2 = merged_df[f'nodes_{engine2_name}'].mean()
    avg_time_engine1 = merged_df[f'execution_time_ms_{engine1_name}'].mean()
    avg_time_engine2 = merged_df[f'execution_time_ms_{engine2_name}'].mean()

    print("\nSearch Performance:")
    print(f"{'Metric':<20} | {'Engine 1 (' + engine1_name + ')':<25} | {'Engine 2 (' + engine2_name + ')' :<25}")
    print(f"{'-' * 20} | {'-' * 25} | {'-' * 25}")
    print(f"{'Average Nodes':<20} | {avg_nodes_engine1:,.2f}{'':<25} | {avg_nodes_engine2:,.2f}")
    print(f"{'Average Time (ms)':<20} | {avg_time_engine1:,.2f}{'':<25} | {avg_time_engine2:,.2f}")

    # --- Average Score Difference ---
    merged_df['score_diff'] = (merged_df[f'score_{engine1_name}'] - merged_df[f'score_{engine2_name}']).abs()
    avg_score_difference = merged_df['score_diff'].mean()

    print("\nEvaluation Comparison:")
    print(f"Average Absolute Score Difference: {avg_score_difference:.2f}")


def analyze_benchmarks(db_path: str):
    """
    Connects to the database, runs analysis, and generates tables and plots.
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        return

    # 1. Load data from database into a pandas DataFrame
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql_query(
                "SELECT engine, position, depth, nodes, execution_time_ms, score, move FROM TB_BENCHMARK", conn)
        except pd.io.sql.DatabaseError:
            print("Error: 'TB_BENCHMARK' table not found or does not contain the expected columns.")
            return

    if df.empty:
        print("The benchmark table is empty. No data to analyze.")
        return

    print(f"Loaded {len(df)} benchmark records.")

    # 2. Data Processing and Feature Engineering
    def get_active_god(row):
        turn = row['position'][-4]
        god_g_id, god_b_id = extract_gods_from_position(row['position'])
        active_god_id_str = god_g_id if turn == '1' else god_b_id
        try:
            active_god_id_int = int(active_god_id_str)
            return GOD_MAP.get(active_god_id_int, "UNKNOWN")
        except (ValueError, TypeError):
            return "UNKNOWN"

    df['active_god'] = df.apply(get_active_god, axis=1)
    df['nps'] = (df['nodes'] / (df['execution_time_ms'] / 1000.0)).where(df['execution_time_ms'] > 0, 0)
    df['nps'] = df['nps'].astype(int)

    # 3. Display Aggregated Tables
    sci_formatter = lambda x: f"{x:.2e}" if abs(x) >= 100000 else f"{int(x):,}"

    print("\n--- Analysis by Depth ---")
    depth_summary = df.groupby(['engine', 'depth']).agg(
        avg_nodes=('nodes', 'mean'),
        median_nodes=('nodes', 'median'),
        avg_time_ms=('execution_time_ms', 'mean'),
        median_time_ms=('execution_time_ms', 'median'),
        avg_nps=('nps', 'mean'),
        median_nps=('nps', 'median'),
        num_positions=('position', 'count')
    ).round(0)
    depth_formatters = {
        'avg_nodes': sci_formatter, 'median_nodes': sci_formatter,
        'avg_time_ms': sci_formatter, 'median_time_ms': sci_formatter,
        'avg_nps': sci_formatter, 'median_nps': sci_formatter,
    }
    print(depth_summary.to_string(formatters=depth_formatters))

    print("\n--- Analysis by Active God (at max depth) ---")
    max_depth = df['depth'].max()
    god_summary = df[df['depth'] == max_depth].groupby(['engine', 'active_god']).agg(
        avg_nodes=('nodes', 'mean'),
        median_nodes=('nodes', 'median'),
        avg_time_ms=('execution_time_ms', 'mean'),
        median_time_ms=('execution_time_ms', 'median'),
        avg_nps=('nps', 'mean'),
        median_nps=('nps', 'median'),
        avg_score=('score', 'mean'),
        median_score=('score', 'median'),
        num_positions=('position', 'count')
    ).round(2)
    god_formatters = {
        **depth_formatters,
        'avg_score': '{:,.2f}'.format,
        'median_score': '{:,.2f}'.format
    }
    print(god_summary.to_string(formatters=god_formatters))

    # 4. Generate and Save Plots
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    print(f"\nGenerating plots in '{OUTPUT_DIR}/' directory...")
    plt.style.use('seaborn-v0_8-whitegrid')

    # Plot 1: Average Nodes by God
    plt.figure(figsize=(12, 7))
    sns.barplot(data=god_summary.reset_index(), x='active_god', y='avg_nodes', hue='engine')
    plt.title(f'Average Nodes Searched by God (Depth {max_depth})')
    plt.ylabel('Average Nodes')
    plt.xlabel('Active God')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'avg_nodes_by_god.png'))
    plt.close()

    # Plot 2: Average Execution Time by God
    plt.figure(figsize=(12, 7))
    sns.barplot(data=god_summary.reset_index(), x='active_god', y='avg_time_ms', hue='engine')
    plt.title(f'Average Execution Time by God (Depth {max_depth})')
    plt.ylabel('Average Time (ms)')
    plt.xlabel('Active God')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'avg_time_by_god.png'))
    plt.close()

    # Plot 3: NPS vs. Depth
    plt.figure(figsize=(12, 7))
    sns.lineplot(data=df, x='depth', y='nps', hue='engine', marker='o', errorbar='sd')
    plt.title('Nodes Per Second (NPS) vs. Search Depth')
    plt.ylabel('Nodes Per Second (NPS)')
    plt.xlabel('Depth')
    plt.grid(True, which="both", ls="--")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'nps_vs_depth.png'))
    plt.close()

    # Plot 4: Score Distribution by God
    plt.figure(figsize=(12, 7))
    sns.boxplot(data=df[df['depth'] == max_depth], x='active_god', y='score', hue='engine')
    plt.title(f'Score Distribution by God (Depth {max_depth})')
    plt.ylabel('Score')
    plt.xlabel('Active God')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'score_dist_by_god.png'))
    plt.close()

    print("Analysis complete. Check the console output and the generated plot images.")

    # --- UPDATED: Per-Depth Engine Comparison ---
    all_engines = df['engine'].unique()

    # 1. Validate the configured engine names
    if ENGINE_1 not in all_engines:
        print(f"\nError: ENGINE_1 name '{ENGINE_1}' not found in the database.")
        print(f"Available engines are: {list(all_engines)}")
        return
    if ENGINE_2 not in all_engines:
        print(f"\nError: ENGINE_2 name '{ENGINE_2}' not found in the database.")
        print(f"Available engines are: {list(all_engines)}")
        return
    if ENGINE_1 == ENGINE_2:
        print(f"\nError: Cannot compare an engine to itself. Please specify two different engines.")
        return

    # 2. Proceed with the comparison using the configured names
    # Get a sorted list of all unique depths in the data
    depths = sorted(df['depth'].unique())
    # Loop through each depth and run the comparison
    for depth in depths:
        compare_engines_per_depth(df, ENGINE_1, ENGINE_2, depth)


if __name__ == '__main__':
    analyze_benchmarks(DB_FILE_PATH)