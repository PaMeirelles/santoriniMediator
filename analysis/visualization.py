import os
from typing import Tuple, Dict

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt, patches, image as mpimg
from collections import defaultdict
from itertools import chain
from sklearn.cluster import KMeans
from constants import TIER_COLORS
from database import get_conn
import statsmodels.api as sm


def load_data(engine_name):
    conn = get_conn()
    query = f"""
        SELECT GOD_G AS God_A, GOD_B AS God_B, result AS Result
        FROM TB_MATCHES
        WHERE Engine_G = '{engine_name}'
          AND Engine_B = '{engine_name}'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["Result"] = df["Result"].astype(int)
    return df


def process_data(df) -> Tuple[Dict, Dict]:
    gods = sorted(set(df["God_A"]).union(set(df["God_B"])))
    matches = {(god_g, god_b): 0 for god_g in gods for god_b in gods if god_g!=god_b}
    wins = {(god_g, god_b): 0 for god_g in gods for god_b in gods if god_g!=god_b}

    for _, row in df.iterrows():
        ga, gb, r = row["God_A"], row["God_B"], row["Result"]
        matches[(ga, gb)] += 1

        if r == 1:
            wins[(ga, gb)] += 1

    return matches, wins

def merge_sides(wins, matches):
    new_wins = wins.copy()
    new_matches = matches.copy()
    gods = sorted(set(chain.from_iterable(matches)))
    for ga in gods:
        for gb in gods:
            if ga == gb: continue
            new_wins[(ga, gb)] += (matches[(gb, ga)] - wins[(gb, ga)])
            new_matches[(ga, gb)] += matches[(gb, ga)]
    return new_wins, new_matches

def calculate_win_rate(matches, wins, side_matters=False):
    if not side_matters:
        wins,matches = merge_sides(wins, matches)
    win_rates = {matchup: wins[matchup] / matches[matchup] for matchup in matches.keys()}
    return win_rates

def consolidate_wr(matches, wins):
    total_games = defaultdict(int)
    total_wins = defaultdict(int)
    for (ga, gb), m in matches.items():
        total_games[ga] += m
        total_games[gb] += m
        total_wins[ga] += wins.get((ga, gb), 0)
        total_wins[gb] += m - wins.get((ga, gb), 0)
    overall_wr = {g: total_wins[g] / total_games[g] for g in total_games if total_games[g] > 0}
    return overall_wr


def calculate_relative_wr(matches, wins):
    god_wr = consolidate_wr(matches, wins)
    win_rates = calculate_win_rate(matches, wins)

    rel_dict = {}

    for (ga, gb), actual_wr in win_rates.items():
        if ga not in god_wr or gb not in god_wr:
            continue

        pA = god_wr[ga]  # overall WR for God A
        pB = god_wr[gb]  # overall WR for God B

        # Convert each to "odds" = p/(1-p). Watch out for p=0.0 or p=1.0 edge cases:
        # (One way is to clamp p slightly, e.g. min=0.001, max=0.999, to avoid divide-by-zero.)
        pA = max(min(pA, 0.999), 0.001)
        pB = max(min(pB, 0.999), 0.001)

        oddsA = pA / (1.0 - pA)
        oddsB = pB / (1.0 - pB)

        expected = oddsA / (oddsA + oddsB)
        rel = actual_wr - expected

        rel_dict[ga, gb] = rel

    return rel_dict

def single_heatmap_plot(
    matrix: pd.DataFrame,
    title: str,
    cmap_name: str = "RdYlGn",
    vmin: float = None,
    vmax: float = None,
    center_0: bool = False,
    value_formatter=lambda x: f"{x:.0f}%",
):
    """
    A single function that draws a heatmap from a given matrix (DataFrame).
    - matrix: a 2D numeric DataFrame (rows/columns = same set of labels).
    - title:  Plot title.
    - cmap_name: which matplotlib colormap to use (e.g. 'RdYlGn', 'bwr', etc.).
    - vmin, vmax: optionally fix the color scale bounds (None => auto).
    - center_0: if True, recenter the color scale around 0 (useful for +/- data).
    - value_formatter: function to format each cell’s numeric value in text.
    """

    gods = matrix.index.tolist()

    # Mask invalid / missing cells
    masked_data = np.ma.masked_invalid(matrix.values)

    # If we want a diverging scale around zero
    if center_0:
        min_val = np.nanmin(masked_data)
        max_val = np.nanmax(masked_data)
        limit = max(abs(min_val), abs(max_val))
        vmin, vmax = -limit, limit

    # Create figure and black background
    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor('black')  # outer frame
    ax.set_facecolor('black')         # plot background

    cmap = plt.get_cmap(cmap_name)
    cmap.set_bad(color='gray')

    # Plot the heatmap
    cax = ax.imshow(masked_data, cmap=cmap, vmin=vmin, vmax=vmax)
    fig.colorbar(cax)

    # Axes label ticks in white
    ax.set_xticks(np.arange(len(gods)))
    ax.set_xticklabels(gods, rotation=90, color='white')
    ax.set_yticks(np.arange(len(gods)))
    ax.set_yticklabels(gods, color='white')

    # Title in white
    ax.set_title(title, color='white', pad=20)

    # Put numeric text in each cell (in black for contrast)
    for i, row_label in enumerate(gods):
        for j, col_label in enumerate(gods):
            val = matrix.loc[row_label, col_label]
            if pd.notna(val):
                ax.text(
                    j, i,
                    value_formatter(val),
                    ha="center", va="center",
                    color="black", fontsize=8
                )

    plt.tight_layout()
    plt.show()

def wr_to_matrix(wr_dict):
    gods = sorted(set(g for pair in wr_dict for g in pair))
    wr_matrix = pd.DataFrame(index=gods, columns=gods, dtype=float)

    for (ga, gb), wr in wr_dict.items():
        wr_matrix.loc[ga, gb] = wr

    return wr_matrix

def plot_normal_heatmap(engine_name, side_matters=False):
    df = load_data(engine_name)
    matches, wins = process_data(df)
    win_rates = calculate_win_rate(matches, wins, side_matters=side_matters)
    wr_matrix = wr_to_matrix(win_rates)

    def pct_formatter(x):  # "75%"
        return f"{x * 100:.0f}%"

    single_heatmap_plot(
        matrix=wr_matrix,
        title=f"{engine_name} – Overall Matchup WR",
        cmap_name="RdYlGn",
        vmin=0,
        vmax=1,
        center_0=False,
        value_formatter=pct_formatter
    )

def plot_relative_heatmap_against_combined_wr(engine_name):
    df = load_data(engine_name)
    matches, wins = process_data(df)
    relative_wr = calculate_relative_wr(matches, wins)
    rel_matrix = wr_to_matrix(relative_wr)

    def plusminus_formatter(x):
        return f"{x * 100:+.1f}%"

    single_heatmap_plot(
        matrix=rel_matrix,
        title=f"{engine_name} – Relative to Expected WR",
        cmap_name="bwr",
        center_0=True,
        value_formatter=plusminus_formatter
    )

def summarize_wr_table(engine_name):
    df = load_data(engine_name)
    matches, wins = process_data(df)

    gods = sorted(set(df["God_A"]).union(df["God_B"]))
    gray_games = {g: 0 for g in gods}
    gray_wins = {g: 0 for g in gods}
    blue_games = {g: 0 for g in gods}
    blue_wins = {g: 0 for g in gods}

    for (ga, gb), count in matches.items():
        gray_games[ga] += count
        blue_games[gb] += count
        gray_wins[ga] += wins.get((ga, gb), 0)
        blue_wins[gb] += count - wins.get((ga, gb), 0)

    rows = []
    for g in gods:
        g_games = gray_games[g]
        b_games = blue_games[g]
        g_wr = gray_wins[g] / g_games if g_games > 0 else np.nan
        b_wr = blue_wins[g] / b_games if b_games > 0 else np.nan
        overall_wr = np.nanmean([g_wr, b_wr])
        wr_diff = g_wr - b_wr
        rows.append((g, g_wr, b_wr, overall_wr, wr_diff))

    # Add total row
    total_g_games = sum(gray_games.values())
    total_b_games = sum(blue_games.values())
    total_g_wr = sum(gray_wins.values()) / total_g_games if total_g_games > 0 else np.nan
    total_b_wr = sum(blue_wins.values()) / total_b_games if total_b_games > 0 else np.nan
    total_overall_wr = np.nanmean([total_g_wr, total_b_wr])
    wr_diff = total_g_wr - total_b_wr
    rows.append(("Total", total_g_wr, total_b_wr, total_overall_wr, wr_diff))

    df_result = pd.DataFrame(rows, columns=["God", "Gray WR", "Blue WR", "Overall WR", "Side Diff"])

    for col in ["Gray WR", "Blue WR", "Overall WR", "Side Diff"]:
        df_result[col] = df_result[col].apply(lambda x: f"{x * 100:.2f}%" if pd.notna(x) else "N/A")

    print(df_result)
    return df_result


def calculate_bradley_terry(engine_name: str):
    df = load_data(engine_name)
    matches, wins = process_data(df)
    rows = []
    for (god_a, god_b), m in matches.items():
        w = wins.get((god_a, god_b), 0)
        rows.append({'god_a': god_a, 'god_b': god_b, 'wins': w, 'matches': m})
    data = pd.DataFrame(rows)
    gods = sorted(set(data['god_a']).union(data['god_b']))
    baseline = gods[0]
    for god in gods:
        if god == baseline:
            continue
        col_name = f"effect_{god}"
        data[col_name] = data.apply(lambda row: 1 if row['god_a'] == god else (-1 if row['god_b'] == god else 0), axis=1)
    X_cols = [f"effect_{god}" for god in gods if god != baseline]
    X = data[X_cols]
    endog = np.column_stack((data['wins'], data['matches'] - data['wins']))
    model = sm.GLM(endog, X, family=sm.families.Binomial())
    result = model.fit()
    b_free = np.array([result.params[f"effect_{god}"] for god in gods if god != baseline])
    b_star = np.concatenate(([0.0], b_free))
    mean_b = b_star.mean()
    ratings = b_star - mean_b
    n = len(gods)
    k = n - 1
    A = np.empty((n, k))
    A[0, :] = -1 / n
    for i in range(1, n):
        A[i, :] = -1 / n
        A[i, i - 1] += 1
    V = result.cov_params().values
    cov_full = A @ V @ A.T
    se_full = np.sqrt(np.diag(cov_full))
    ci_mult = 1.96
    lower = ratings - ci_mult * se_full
    upper = ratings + ci_mult * se_full
    ratings = np.round(ratings, 2)
    se_full = np.round(se_full, 2)
    lower = np.round(lower, 2)
    upper = np.round(upper, 2)
    summary_df = pd.DataFrame({
        'Rating': ratings,
        'SE': se_full,
        'Lower': lower,
        'Upper': upper
    }, index=gods)
    summary_df.sort_values('Rating', ascending=False, inplace=True)
    adjustment = summary_df.iloc[-1]['Rating']
    summary_df['Rating'] = np.round(summary_df['Rating'] - adjustment, 2)
    summary_df['Lower'] = np.round(summary_df['Lower'] - adjustment, 2)
    summary_df['Upper'] = np.round(summary_df['Upper'] - adjustment, 2)
    return summary_df


def cluster_and_assign_tiers(tier_df, n_clusters=5):
    kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(tier_df[["BT_Rating"]])
    tier_labels = ['S', 'A', 'B', 'C', 'D']
    cluster_order = tier_df.groupby(kmeans.labels_)["BT_Rating"].mean().sort_values(ascending=False).index
    cluster_to_tier = {cluster: tier_labels[i] for i, cluster in enumerate(cluster_order)}
    tier_df["Cluster"] = kmeans.labels_
    tier_df["Tier"] = tier_df["Cluster"].map(cluster_to_tier)
    tier_order_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
    tier_df["TierRank"] = tier_df["Tier"].map(tier_order_map)
    tier_df = tier_df.sort_values(by=["TierRank", "WinRate"], ascending=[False, False]).reset_index(drop=True)
    bt_ratings_list = tier_df["BT_Rating"].tolist()
    bt_gap = [round(bt_ratings_list[i] - bt_ratings_list[i + 1], 2) for i in range(len(bt_ratings_list) - 1)] + [0.00]
    tier_df["BT Gap"] = bt_gap
    return tier_df

def ansi_color_text(text, hex_color):
    def hex_to_rgb(hex_color):
        return tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
    r, g, b = hex_to_rgb(hex_color)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def plot_tier_icons(df):
    tier_order = ["S", "A", "B", "C", "D"]
    row_height = 1.0
    gap_height = 0.02
    label_width = 1.0
    vertical_strip_width = 0.02
    icon_width = 1.0
    max_width = 0
    for tier in tier_order:
        subset = df[df["Tier"] == tier]
        n_icons = len(subset)
        row_width = label_width + vertical_strip_width + n_icons * icon_width
        max_width = max(max_width, row_width)
    total_height = len(tier_order) * row_height + (len(tier_order) - 1) * gap_height
    fig, ax = plt.subplots(figsize=(max_width * 1.2, total_height * 1.2))
    fig.patch.set_facecolor("#2c2c2c")
    ax.set_facecolor("#2c2c2c")
    ax.set_xlim(0, max_width)
    ax.set_ylim(0, total_height)
    ax.set_aspect("auto")
    ax.axis("off")
    y_current = total_height
    for i, tier in enumerate(tier_order):
        y_top = y_current
        y_bottom = y_top - row_height
        ax.add_patch(patches.Rectangle((0, y_bottom), label_width, row_height, facecolor=TIER_COLORS[tier]))
        ax.text(label_width / 2, (y_bottom + y_top) / 2, tier, color="black", fontsize=30, ha="center", va="center")
        ax.add_patch(patches.Rectangle((label_width, y_bottom), vertical_strip_width, row_height, facecolor="black"))
        subset = df[df["Tier"] == tier].sort_values("WinRate", ascending=False)
        x_current = label_width + vertical_strip_width
        for god in subset["God"]:
            image_path = None
            for ext in (".png", ".jpg", ".jpeg"):
                candidate = f"god_icons/{god}{ext}"
                if os.path.exists(candidate):
                    image_path = candidate
                    break
            if not image_path:
                print(f"Missing icon for {god}")
                continue
            ax.imshow(mpimg.imread(image_path), extent=(x_current, x_current + icon_width, y_bottom, y_top))
            x_current += icon_width
        if i < len(tier_order) - 1:
            y_current = y_bottom - gap_height
            ax.add_patch(patches.Rectangle((0, y_current), max_width, gap_height, facecolor="black"))
        else:
            y_current = y_bottom
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.show()


def print_consolidated_table(engine_name: str):
    # Load data and compute overall win rate
    df = load_data(engine_name)
    matches, wins = process_data(df)
    overall_wr = consolidate_wr(matches, wins)

    # Compute BT ratings and map overall win rate
    bt_df = calculate_bradley_terry(engine_name).reset_index().rename(columns={"index": "God"})
    bt_df["WinRate"] = bt_df["God"].map(overall_wr)
    bt_df.rename(columns={"Rating": "BT_Rating"}, inplace=True)

    # Cluster BT ratings to assign tiers
    consolidated = cluster_and_assign_tiers(bt_df, n_clusters=5)
    final_table = consolidated[["God", "WinRate", "BT_Rating", "SE", "Lower", "Upper", "Tier"]]

    # Prepare headers and data for printing
    headers = ["God", "Win Rate", "BT Rating", "SE", "Lower", "Upper", "Tier"]
    data = []
    for _, row in final_table.iterrows():
        data.append([
            row["God"],
            f"{row['WinRate'] * 100:.1f}%",
            f"{row['BT_Rating']:.2f}",
            f"{row['SE']:.2f}" if pd.notna(row['SE']) else "N/A",
            f"{row['Lower']:.2f}" if pd.notna(row['Lower']) else "N/A",
            f"{row['Upper']:.2f}" if pd.notna(row['Upper']) else "N/A",
            row["Tier"]
        ])

    # Calculate column widths
    col_widths = [max(len(str(x)) for x in [header] + [row[i] for row in data])
                  for i, header in enumerate(headers)]
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    # Print header row
    print(sep)
    header_row = "| " + " | ".join(header.ljust(col_widths[i]) for i, header in enumerate(headers)) + " |"
    print(header_row)
    print(sep)

    # Print each data row with colored Tier column
    for row in data:
        row[6] = ansi_color_text(row[6].ljust(col_widths[6]), TIER_COLORS[row[6]])
        print("| " + " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(headers))) + " |")
    print(sep)

    return final_table

if __name__ == "__main__":
    engine = "Fitos_4.6_Atium"
    plot_normal_heatmap(engine, side_matters=False)
    plot_normal_heatmap(engine, side_matters=True)
    plot_relative_heatmap_against_combined_wr(engine)
    summarize_wr_table(engine)
    tier_table = print_consolidated_table(engine)
    plot_tier_icons(tier_table)