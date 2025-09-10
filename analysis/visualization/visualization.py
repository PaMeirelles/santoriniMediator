import os
from typing import Tuple, Dict, List

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt, patches, image as mpimg
from collections import defaultdict
from itertools import chain
from sklearn.cluster import KMeans
from game.constants import TIER_COLORS
from analysis.database import get_conn
import statsmodels.api as sm


def load_data(engine_a: str, engine_b: str="") -> pd.DataFrame:
    if engine_b == "":
        engine_b = engine_a
    conn = get_conn()
    query = f"""
        SELECT Id, GOD_G AS God_A, GOD_B AS God_B, result AS Result, Engine_G, Engine_B, Starting_pos
        FROM TB_MATCHES
        WHERE ((Engine_G = '{engine_a}' AND Engine_B = '{engine_b}')
           OR (Engine_G = '{engine_b}' AND Engine_B = '{engine_a}')) AND Time_G = 60
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
    win_rates = {
        matchup: wins[matchup] / matches[matchup]
        for matchup in matches.keys()
        if matches[matchup] > 0  # Protect against division by zero
    }
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

def get_contextual_wr(god_to_measure, opponent_to_exclude, all_matches, all_wins):
    """
    Calculates a god's win rate against all opponents EXCEPT the one specified.
    """
    contextual_games = 0
    contextual_wins = 0

    # Iterate through all matchups to find games involving the god_to_measure
    for (ga, gb), matches_count in all_matches.items():
        if matches_count == 0:
            continue

        # Case 1: god_to_measure is God A
        if ga == god_to_measure and gb != opponent_to_exclude:
            contextual_games += matches_count
            contextual_wins += all_wins.get((ga, gb), 0)

        # Case 2: god_to_measure is God B
        if gb == god_to_measure and ga != opponent_to_exclude:
            contextual_games += matches_count
            # Wins for God B are games - wins for God A
            contextual_wins += matches_count - all_wins.get((ga, gb), 0)

    if contextual_games == 0:
        return 0.5 # Return a neutral 50% if no other games exist

    return contextual_wins / contextual_games


def calculate_matchup_advantage_contextual(matches, wins):
    """
    Calculates the matchup advantage using the robust "Leave-One-Out" method.
    """
    win_rates = calculate_win_rate(matches, wins) # Actual matchup WRs
    advantage_dict = {}

    for (ga, gb), actual_wr in win_rates.items():
        # Step 1 & 2: Get the contextual WR for each god
        pA_contextual = get_contextual_wr(ga, gb, matches, wins)
        pB_contextual = get_contextual_wr(gb, ga, matches, wins)

        # Step 3: Calculate the much fairer baseline
        baseline = (pA_contextual + (1 - pB_contextual)) / 2

        # Step 4: Calculate the final advantage score
        advantage = actual_wr - baseline
        advantage_dict[ga, gb] = advantage

    return advantage_dict

def single_heatmap_plot(
    matrix: pd.DataFrame,
    title: str,
    count_matrix: pd.DataFrame = None,  # <--- NEW: Accept a matrix of game counts
    cmap_name: str = "RdYlGn",
    vmin: float = None,
    vmax: float = None,
    center_0: bool = False,
    value_formatter=lambda x: f"{x:.0f}%",
):
    gods = matrix.index.tolist()

    if center_0:
        min_val = np.nanmin(matrix.values)
        max_val = np.nanmax(matrix.values)
        limit = max(abs(min_val), abs(max_val)) if pd.notna(min_val) else 1
        vmin, vmax = -limit, limit

    fig, ax = plt.subplots(figsize=(12, 10))  # Slightly larger for better text fit
    fig.patch.set_facecolor('black')
    ax.set_facecolor('black')
    n_gods = len(gods)
    ax.set_xlim(-0.5, n_gods - 0.5)
    ax.set_ylim(-0.5, n_gods - 0.5)
    cmap = plt.get_cmap(cmap_name)
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    # --- START of new logic ---
    # Instead of imshow, we loop to draw each cell with custom alpha
    max_count_log = 0
    if count_matrix is not None and not count_matrix.empty:
        max_val = count_matrix.max().max()
        if pd.notna(max_val) and max_val > 0:
            max_count_log = np.log1p(max_val)

    for i, row_label in enumerate(gods):
        for j, col_label in enumerate(gods):
            val = matrix.loc[row_label, col_label]
            if pd.isna(val):
                ax.add_patch(patches.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor='gray', edgecolor='black'))
                continue

            alpha = 1.0
            count = 0
            if count_matrix is not None:
                count = count_matrix.loc[row_label, col_label]
                if pd.notna(count) and count > 0 and max_count_log > 0:
                    # Scale alpha from 0.3 to 1.0 using a log scale for better visual separation
                    alpha = 0.3 + 0.7 * (np.log1p(count) / max_count_log)

            color = cmap(norm(val))
            ax.add_patch(patches.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=color, alpha=alpha, edgecolor='black'))

            # Update text to include the count on a new line
            text_val = value_formatter(val)
            if count_matrix is not None and pd.notna(count):
                text_val += f"\n({int(count)})"

            ax.text(j, i, text_val, ha="center", va="center", color="black", fontsize=12)

    # Create a mappable for the colorbar since we aren't using imshow
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    fig.colorbar(sm, ax=ax)
    # --- END of new logic ---

    ax.set_xticks(np.arange(len(gods)))
    ax.set_xticklabels(gods, rotation=90, color='white')
    ax.set_yticks(np.arange(len(gods)))
    ax.set_yticklabels(gods, color='white')
    ax.set_title(title, color='white', pad=20)
    ax.invert_yaxis()  # Match imshow's top-left origin

    plt.tight_layout()
    plt.show()

def dict_to_matrix(wr_dict):
    gods = sorted(set(g for pair in wr_dict for g in pair))
    wr_matrix = pd.DataFrame(index=gods, columns=gods, dtype=float)

    for (ga, gb), wr in wr_dict.items():
        wr_matrix.loc[ga, gb] = wr

    return wr_matrix

def plot_normal_heatmap(engine_name, side_matters=False):
    df = load_data(engine_name)
    matches, wins = process_data(df)

    # 1. Calculate overall win rates to determine the sorting order
    overall_wr = consolidate_wr(matches, wins)
    sorted_gods = sorted(overall_wr, key=overall_wr.get, reverse=True)

    plot_matches = matches
    if not side_matters:
        # Important: merge_sides returns (new_wins, new_matches)
        _, plot_matches = merge_sides(wins, matches)

    win_rates = calculate_win_rate(matches, wins, side_matters=side_matters)
    wr_matrix = dict_to_matrix(win_rates)
    count_matrix = dict_to_matrix(plot_matches) # Create the count matrix

    wr_matrix = wr_matrix.reindex(index=sorted_gods, columns=sorted_gods)
    count_matrix = count_matrix.reindex(index=sorted_gods, columns=sorted_gods)

    def pct_formatter(x):  # "75%"
        return f"{x * 100:.0f}%"

    single_heatmap_plot(
        matrix=wr_matrix,
        count_matrix=count_matrix,
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

    # 1. Calculate overall win rates to determine the sorting order
    overall_wr = consolidate_wr(matches, wins)
    sorted_gods = sorted(overall_wr, key=overall_wr.get, reverse=True)

    relative_wr = calculate_matchup_advantage_contextual(matches, wins)
    rel_matrix = dict_to_matrix(relative_wr)
    count_matrix = dict_to_matrix(matches) # Create the count matrix

    rel_matrix = rel_matrix.reindex(index=sorted_gods, columns=sorted_gods)
    count_matrix = count_matrix.reindex(index=sorted_gods, columns=sorted_gods)

    def plusminus_formatter(x):
        return f"{x * 100:+.1f}%"

    single_heatmap_plot(
        matrix=rel_matrix,
        count_matrix=count_matrix,
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
    data = data[data['matches'] > 0].copy()

    gods = sorted(set(data['god_a']).union(set(data['god_b'])))

    # Protect against empty data
    if not gods:
        return pd.DataFrame(columns=['Rating', 'SE', 'Lower', 'Upper'])

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

    # This should be safe now because we checked if gods is empty
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
    # Protect against empty DataFrame
    if tier_df.empty:
        return pd.DataFrame(columns=list(tier_df.columns) + ["Cluster", "Tier", "TierRank", "BT Gap"])

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
                candidate = f"../god_icons/{god}{ext}"
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


def calculate_bradley_terry_multiple(engines: List[str]):
    """
    MODIFIED: This version uses Additive Smoothing for guaranteed numerical
    stability and an efficient method for creating the model matrix.
    """
    all_dfs = [load_data(e1, e2) for i, e1 in enumerate(engines) for e2 in engines[i:]]
    df = pd.concat(all_dfs, ignore_index=True)

    df["Player_G"] = df["God_A"] + "@" + df["Engine_G"]
    df["Player_B"] = df["God_B"] + "@" + df["Engine_B"]

    df["Winner"] = df.apply(
        lambda row: row["Player_G"] if row["Result"] >= 1 else row["Player_B"], axis=1
    )
    df["Loser"] = df.apply(
        lambda row: row["Player_B"] if row["Result"] <= 1 else row["Player_G"], axis=1
    )

    win_counts = df.groupby(["Winner", "Loser"]).size().reset_index(name="Wins")
    losses = win_counts.rename(columns={"Winner": "Loser", "Loser": "Winner", "Wins": "Losses"})
    merged = pd.merge(win_counts, losses, on=["Winner", "Loser"], how="outer").fillna(0)
    merged["Matches"] = merged["Wins"] + merged["Losses"]

    players = sorted(set(merged["Winner"]).union(set(merged["Loser"])))
    if not players:
        return pd.DataFrame(columns=['Rating', 'SE', 'Lower', 'Upper'])

    baseline = players[0]

    # --- STABILITY FIX: Additive (Laplace) Smoothing ---
    # Add 0.5 "ghost wins" to prevent 0% or 100% win rates. This is the
    # key to stopping the ratings from exploding to infinity.
    smoothing_alpha = 0.5
    merged["Wins"] += smoothing_alpha
    merged["Matches"] += 2 * smoothing_alpha  # Add one full "ghost game"
    # --- END FIX ---

    # --- PERFORMANCE FIX: Create all effect columns at once ---
    player_cols = [p for p in players if p != baseline]
    effects_data = []
    for _, row in merged.iterrows():
        effect_row = {}
        for p in player_cols:
            if row["Winner"] == p:
                effect_row[f"effect_{p}"] = 1
            elif row["Loser"] == p:
                effect_row[f"effect_{p}"] = -1
            else:
                effect_row[f"effect_{p}"] = 0
        effects_data.append(effect_row)

    effects_df = pd.DataFrame(effects_data, index=merged.index)

    X_cols = list(effects_df.columns)
    X = effects_df[X_cols]

    # We now model the smoothed wins and matches
    endog = np.column_stack((merged["Wins"], merged["Matches"] - merged["Wins"]))

    model = sm.GLM(endog, X, family=sm.families.Binomial())
    result = model.fit()  # Regularization is no longer needed with smoothing
    # --- END FIX ---

    b_free = np.array([result.params.get(f"effect_{p}", 0) for p in players if p != baseline])
    b_star = np.concatenate(([0.0], b_free))
    mean_b = b_star.mean()
    ratings = b_star - mean_b

    n_players = len(players)
    A = np.empty((n_players, n_players - 1))
    A[0, :] = -1 / n_players
    for i in range(1, n_players):
        A[i, :] = -1 / n_players
        A[i, i - 1] += 1

    V = result.cov_params().values
    cov_full = A @ V @ A.T
    se_full = np.sqrt(np.diag(cov_full))
    ci_mult = 1.96
    lower = ratings - ci_mult * se_full
    upper = ratings + ci_mult * se_full

    summary_df = pd.DataFrame({
        'Rating': np.round(ratings - ratings.min(), 2),
        'SE': np.round(se_full, 2),
        'Lower': np.round(lower - ratings.min(), 2),
        'Upper': np.round(upper - ratings.min(), 2)
    }, index=players).sort_values("Rating", ascending=False)

    return summary_df

if __name__ == "__main__":
    engine = "Paladini_4.1.1_Mystic"
    plot_normal_heatmap(engine, side_matters=False)
    plot_normal_heatmap(engine, side_matters=True)
    plot_relative_heatmap_against_combined_wr(engine)
    summarize_wr_table(engine)
    tier_table = print_consolidated_table(engine)
    plot_tier_icons(tier_table)
    # print(calculate_bradley_terry_multiple(["Fitos_6.3_Trick", "Fitos_7.2_Time"]))