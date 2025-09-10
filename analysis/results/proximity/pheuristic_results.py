import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- Configuration ---
INPUT_CSV_PATH = "distance_analysis_true_all_states.csv"
OUTPUT_PLOT_PATH = "heuristic_analysis_plots_true_dist.png"


def analyze_and_plot_results(csv_path: str):
    """
    Loads the analysis CSV, calculates differences and plots a comprehensive
    dashboard comparing Naive, A* (Pan), and True (God-specific) distances.
    """
    print(f"Loading analysis data from '{csv_path}'...")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: The file '{csv_path}' was not found.")
        print("Please run the 'analyze_distance_true.py' script first to generate the data.")
        return

    print("Data loaded. Calculating differences and preparing plots...")

    # --- Data Preparation: Compare both heuristics to the True Distance ---
    df.replace(float('inf'), np.inf, inplace=True)
    # Error of Naive Heuristic = True Distance - Naive Distance
    df['diff_naive_g'] = df['true_dist_g'] - df['naive_dist_g']
    df['diff_naive_b'] = df['true_dist_b'] - df['naive_dist_b']
    # Error of A* (Pan) Heuristic = True Distance - A* (Pan) Distance
    df['diff_astar_g'] = df['true_dist_g'] - df['a_star_dist_g']
    df['diff_astar_b'] = df['true_dist_b'] - df['a_star_dist_b']

    # --- Plotting Setup (2x2 Grid) ---
    plt.style.use('seaborn-v0_8-whitegrid')
    fig = plt.figure(figsize=(22, 18))
    gs = fig.add_gridspec(2, 2)

    ax_hist = fig.add_subplot(gs[0, 0])
    ax_box = fig.add_subplot(gs[0, 1])
    ax_line = fig.add_subplot(gs[1, 0])
    ax_table = fig.add_subplot(gs[1, 1])

    fig.suptitle('Heuristic Performance Analysis vs. True Distance', fontsize=22)

    # --- Plot 1: Histogram of Heuristic Errors ---
    # Correctly filter for only finite values, excluding inf and NaN
    all_diffs_naive = pd.concat([df['diff_naive_g'], df['diff_naive_b']])
    finite_diffs_naive = all_diffs_naive[np.isfinite(all_diffs_naive)]

    all_diffs_astar = pd.concat([df['diff_astar_g'], df['diff_astar_b']])
    finite_diffs_astar = all_diffs_astar[np.isfinite(all_diffs_astar)]

    # Create shared bins to align both histograms, checking for empty data
    if not finite_diffs_naive.empty or not finite_diffs_astar.empty:
        min_vals, max_vals = [], []
        if not finite_diffs_naive.empty:
            min_vals.append(finite_diffs_naive.min())
            max_vals.append(finite_diffs_naive.max())
        if not finite_diffs_astar.empty:
            min_vals.append(finite_diffs_astar.min())
            max_vals.append(finite_diffs_astar.max())

        min_bin = int(min(min_vals)) - 1
        max_bin = int(max(max_vals)) + 1
        bins = np.arange(min_bin, max_bin, 1)

        ax_hist.hist(finite_diffs_naive, bins=bins, alpha=0.7, label='Naive Heuristic Error', color='skyblue',
                     edgecolor='darkblue')
        ax_hist.hist(finite_diffs_astar, bins=bins, alpha=0.7, label='A* (Pan) Heuristic Error', color='lightcoral',
                     edgecolor='darkred')

    ax_hist.set_title('Histogram of Heuristic Error (vs. True Distance)', fontsize=16)
    ax_hist.set_xlabel('Difference (True - Heuristic)', fontsize=12)
    ax_hist.set_ylabel('Frequency', fontsize=12)
    ax_hist.legend()
    ax_hist.grid(True, which='both', linestyle='--', linewidth=0.5)

    # --- Plot 2: Boxplots of Calculation Times ---
    time_data = [df['naive_time_s'], df['a_star_time_s'], df['true_time_s']]
    labels = ['Naive Time', 'A* (Pan) Time', 'True (God) Time']

    box = ax_box.boxplot(time_data, labels=labels, vert=True, patch_artist=True, whis=[5, 95], showfliers=False)

    colors = ['lightblue', 'lightgreen', 'lightcoral']
    for patch, color in zip(box['boxes'], colors):
        patch.set_facecolor(color)

    ax_box.set_yscale('log')
    ax_box.set_title('Comparison of Calculation Times per Board State', fontsize=16)
    ax_box.set_ylabel('Time (seconds, log scale)', fontsize=12)
    ax_box.grid(True, which='both', linestyle='--', linewidth=0.5)

    # --- Plot 3: Average of DIFFERENCES vs. Move Count ---
    # Melt both sets of differences
    melted_naive = df.melt(id_vars=['ply_number'], value_vars=['diff_naive_g', 'diff_naive_b'], value_name='diff_naive')
    melted_astar = df.melt(id_vars=['ply_number'], value_vars=['diff_astar_g', 'diff_astar_b'], value_name='diff_astar')
    melted_true = df.melt(id_vars=['ply_number'], value_vars=['true_dist_g', 'true_dist_b'], value_name='true_dist')

    # Calculate average of finite differences
    avg_naive_by_ply = melted_naive[np.isfinite(melted_naive['diff_naive'])].groupby('ply_number')['diff_naive'].mean().reset_index()
    avg_astar_by_ply = melted_astar[np.isfinite(melted_astar['diff_astar'])].groupby('ply_number')['diff_astar'].mean().reset_index()

    # Calculate unreachable rate based on the true distance
    melted_true['is_unreachable'] = melted_true['true_dist'] == np.inf
    unreachable_rate_by_ply = melted_true.groupby('ply_number')['is_unreachable'].mean().reset_index()

    # Corrected, robust merging logic
    all_plies = pd.DataFrame({'ply_number': df['ply_number'].unique()})
    plot_data = pd.merge(all_plies, avg_naive_by_ply, on='ply_number', how='left')
    plot_data = pd.merge(plot_data, avg_astar_by_ply, on='ply_number', how='left')
    plot_data = pd.merge(plot_data, unreachable_rate_by_ply.rename(columns={'is_unreachable': 'unreachable_rate'}),
                         on='ply_number', how='left')

    # Plot lines on primary y-axis
    l1 = ax_line.plot(plot_data['ply_number'], plot_data['diff_naive'], marker='.', linestyle='--',
                      label='Avg. Naive Error', color='deepskyblue')
    l2 = ax_line.plot(plot_data['ply_number'], plot_data['diff_astar'], marker='o', linestyle='-',
                      label='Avg. A* (Pan) Error', color='purple')
    ax_line.axhline(0, color='black', linestyle=':', linewidth=1.0, label='Perfect Heuristic (Error = 0)')

    ax_line.set_title('Average Heuristic Error & Unreachable Rate vs. Move Count', fontsize=16)
    ax_line.set_xlabel('Ply Number (Move Count)', fontsize=12)
    ax_line.set_ylabel('Average Difference (True - Heuristic)', fontsize=12, color='purple')
    ax_line.tick_params(axis='y', labelcolor='purple')

    # Plot bars on secondary y-axis
    ax_unreachable = ax_line.twinx()
    bar1 = ax_unreachable.bar(plot_data['ply_number'], plot_data['unreachable_rate'] * 100, alpha=0.25, color='gray',
                              label='Unreachable Rate')
    ax_unreachable.set_ylabel('Unreachable States (%)', fontsize=12, color='gray')
    ax_unreachable.tick_params(axis='y', labelcolor='gray')
    ax_unreachable.set_ylim(0, 100)

    # Combine legends
    lines = l1 + l2 + [ax_line.get_lines()[0]]
    labels = [l.get_label() for l in lines]
    ax_line.legend(lines + [bar1], labels + [bar1.get_label()], loc='upper left')

    # --- Plot 4: Table with Processing Time ---
    ax_table.axis('off')
    ax_table.set_title("Processing Time Summary", fontsize=16)

    total_naive_time = df['naive_time_s'].sum()
    total_a_star_time = df['a_star_time_s'].sum()
    total_true_time = df['true_time_s'].sum()
    total_analysis_time = total_naive_time + total_a_star_time + total_true_time
    avg_naive_time_us = df['naive_time_s'].mean() * 1e6
    avg_a_star_time_us = df['a_star_time_s'].mean() * 1e6
    avg_true_time_us = df['true_time_s'].mean() * 1e6
    num_states_processed = len(df)

    table_data = [
        [f"{total_naive_time:.2f} s", f"{avg_naive_time_us:.1f} µs"],
        [f"{total_a_star_time:.2f} s", f"{avg_a_star_time_us:.1f} µs"],
        [f"{total_true_time:.2f} s", f"{avg_true_time_us:.1f} µs"],
        [f"{total_analysis_time:.2f} s", "-"],
        [f"{num_states_processed}", "-"]
    ]

    row_labels = ["Naive", "A* (Pan)", "True (God)", "Overall Total", "States Processed"]
    col_labels = ["Total Time", "Avg. Time / State"]

    table = ax_table.table(cellText=table_data, rowLabels=row_labels, colLabels=col_labels, loc='center',
                           cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.1, 2.0)

    # --- Final Formatting and Saving ---
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(OUTPUT_PLOT_PATH)
    print(f"Plots saved to '{OUTPUT_PLOT_PATH}'")
    plt.show()


if __name__ == "__main__":
    analyze_and_plot_results(INPUT_CSV_PATH)

