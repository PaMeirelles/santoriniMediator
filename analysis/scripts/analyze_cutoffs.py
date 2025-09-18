import pandas as pd
import sys


def run_analysis_on_subset(df, title):
    """Helper function to run the cutoff analysis on a dataframe subset."""

    print(f"\n{'---' * 10}")
    print(f"--- {title} ---")
    print(f"{'---' * 10}")

    total_cutoffs = len(df)
    if total_cutoffs == 0:
        print("No data in this subset to analyze.")
        return

    # --- Analysis of TT and Killer Moves ---
    tt_cutoffs = df['IsTTMove'].sum()
    killer_cutoffs = df['IsKillerMove'].sum()

    tt_percentage = (tt_cutoffs / total_cutoffs) * 100
    killer_percentage = (killer_cutoffs / total_cutoffs) * 100

    print("\n--- Cutoff Source Analysis ---")
    print(f"Total Cutoffs Logged: {total_cutoffs}")
    print(f"Caused by TT Move:    {tt_cutoffs} ({tt_percentage:.2f}%)")
    print(f"Caused by Killer Move: {killer_cutoffs} ({killer_percentage:.2f}%)")

    # --- Cumulative Percentage Table ---
    move_counts = df[df['IsTTMove'] == 0]['MoveIndex'].value_counts().sort_index()
    non_tt_cutoffs = total_cutoffs - tt_cutoffs

    if non_tt_cutoffs == 0:
        print("\nNo non-TT cutoffs to analyze for the cumulative table.")
        return

    print("\n--- Cumulative Cutoff Percentage per Move Index ---")
    print("(Excludes TT moves, which have an index of 0)")
    print("+------------------------------------------------------+")
    print("| First 'n' Moves | Cumulative Cutoffs | Cumulative %  |")
    print("+------------------------------------------------------+")

    cumulative_count = 0
    max_n_to_display = min(20, move_counts.index.max() if not move_counts.empty else 1)

    for n in range(1, max_n_to_display + 1):
        current_n_count = move_counts.get(n, 0)
        cumulative_count += current_n_count
        percentage = (cumulative_count / non_tt_cutoffs) * 100
        print(f"| <= {n:<14} | {cumulative_count:<18} | {percentage:>11.2f}% |")

    print("+------------------------------------------------------+")


def analyze_cutoffs_by_depth(filepath="../../data/cutoff_log.csv"):
    """
    Reads a cutoff log and analyzes it by separating internal and frontier search nodes.
    """
    try:
        df = pd.read_csv(filepath, dtype=int, on_bad_lines='skip')
    except (FileNotFoundError, pd.errors.EmptyDataError) as e:
        print(f"Error reading file: {e}")
        return

    df.dropna(inplace=True)
    df = df.astype(int)

    if df.empty:
        print("Log file contains no valid data to analyze.")
        return

    # --- Separate data into two groups ---
    # Internal nodes are those that are not at the edge of the search
    df_internal = df[df['Depth'] > 1]
    # Frontier nodes are at the maximum ply for an iteration (remaining depth is 1)
    df_frontier = df[df['Depth'] == 1]

    # --- Run and print analysis for each group ---
    run_analysis_on_subset(df_internal, "INTERNAL NODE ANALYSIS (Depth > 1)")
    run_analysis_on_subset(df_frontier, "FRONTIER NODE ANALYSIS (Depth == 1)")


if __name__ == "__main__":
    analyze_cutoffs_by_depth()