#!/usr/bin/env python3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from collections import defaultdict
import sqlite3
import os
import matplotlib.image as mpimg
import matplotlib.patches as patches
import statsmodels.api as sm

DB_PATH = "../data/matches.db"
ENGINE_NAME = "Fitos_3.2_Life"

TIER_COLORS = {
    'S': '#FF6C6C',
    'A': '#FFBC7D',
    'B': '#FFE780',
    'C': '#FFFFA0',
    'D': '#B8FF84'
}

def load_data(db_path, engine_name):
    conn = sqlite3.connect(db_path)
    query = f"""
        SELECT GOD_G AS God_A, God_B AS God_B, result AS Result
        FROM TB_MATCHES
        WHERE Engine_G = '{ENGINE_NAME}'
        AND Engine_B = '{ENGINE_NAME}'
        AND Date IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["Result"] = df["Result"].astype(int)
    return df

def compute_matchup_stats(df):
    gods = sorted(set(df["God_A"]).union(set(df["God_B"])))
    win_counts = {god: 0 for god in gods}
    loss_counts = {god: 0 for god in gods}

    matchup_matches = pd.DataFrame(0, index=gods, columns=gods)
    matchup_wins = pd.DataFrame(0, index=gods, columns=gods)

    for _, row in df.iterrows():
        ga, gb, r = row["God_A"], row["God_B"], row["Result"]
        if r == 1:
            win_counts[ga] += 1
            loss_counts[gb] += 1
        elif r == -1:
            win_counts[gb] += 1
            loss_counts[ga] += 1

        matchup_matches.loc[ga, gb] += 1
        matchup_matches.loc[gb, ga] += 1

        if r == 1:
            matchup_wins.loc[ga, gb] += 1
        elif r == -1:
            matchup_wins.loc[gb, ga] += 1

    return gods, win_counts, loss_counts, matchup_matches, matchup_wins

def compute_winrates(gods, win_counts, loss_counts, matchup_matches, matchup_wins):
    winrates = {}
    for g in gods:
        total = win_counts[g] + loss_counts[g]
        winrates[g] = (win_counts[g] / total) if total else 0

    matchup_wr = matchup_wins.divide(matchup_matches).fillna(0)
    for i in range(len(gods)):
        matchup_wr.iloc[i, i] = np.nan

    return winrates, matchup_wr

def compute_bt_with_confidence(df):
    data = []
    for _, row in df.iterrows():
        ga, gb, r = row["God_A"], row["God_B"], row["Result"]
        if r == 1:
            winner, loser = ga, gb
        elif r == -1:
            winner, loser = gb, ga
        else:
            continue
        data.append((winner, loser))

    df_bt = pd.DataFrame(data, columns=["winner", "loser"])
    gods = sorted(set(df_bt["winner"]) | set(df_bt["loser"]))

    god_to_idx = {g: i for i, g in enumerate(gods)}
    rows = []
    outcomes = []

    for _, row in df_bt.iterrows():
        winner_idx = god_to_idx[row["winner"]]
        loser_idx = god_to_idx[row["loser"]]
        row_vec = [0] * len(gods)
        row_vec[winner_idx] = 1
        row_vec[loser_idx] = -1
        rows.append(row_vec)
        outcomes.append(1)

    X = pd.DataFrame(rows, columns=gods)
    y = pd.Series(outcomes)

    baseline = X.columns[0]
    X = X.drop(columns=[baseline])

    model = sm.Logit(y, X)
    result = model.fit(disp=False)

    coefs = result.params
    coefs[baseline] = 0.0
    bt_ratings = coefs.to_dict()

    se = result.bse
    se[baseline] = 0.0
    bt_std = se.to_dict()

    min_score = min(bt_ratings.values())
    for g in bt_ratings:
        bt_ratings[g] -= min_score

    return bt_ratings, bt_std

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
    bt_gap = [round(bt_ratings_list[i] - bt_ratings_list[i + 1], 2)
              for i in range(len(bt_ratings_list) - 1)] + [0.00]
    tier_df["BT Gap"] = bt_gap

    return tier_df

def hex_to_rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))

def ansi_color_text(text, hex_color):
    r, g, b = hex_to_rgb(hex_color)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

def print_pretty_table_with_gap(df, tier_colors):
    headers = ["God", "Win Rate", "BT Rating", "BT SE", "BT Gap", "Tier"]
    data = []
    for _, row in df.iterrows():
        data.append([
            row["God"],
            f"{row['WinRate'] * 100:.1f}%",
            f"{row['BT_Rating']:.2f}",
            f"{row['BT_SE']:.3f}",
            f"{row['BT Gap']:.2f}",
            row["Tier"]
        ])

    col_widths = [max(len(str(cell)) for cell in [header] + [row[i] for row in data])
                  for i, header in enumerate(headers)]
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    print(sep)
    print("| " + " | ".join(header.ljust(col_widths[i]) for i, header in enumerate(headers)) + " |")
    print(sep)

    for row in data:
        tier_col = ansi_color_text(row[5].ljust(col_widths[5]), TIER_COLORS[row[5]])
        parts = row[:5] + [tier_col]
        print("| " + " | ".join(str(parts[i]).ljust(col_widths[i]) for i in range(6)) + " |")
    print(sep)

def main():
    df = load_data(DB_PATH, ENGINE_NAME)
    gods, win_counts, loss_counts, matchup_matches, matchup_wins = compute_matchup_stats(df)
    winrates, matchup_wr = compute_winrates(gods, win_counts, loss_counts, matchup_matches, matchup_wins)

    # Use new BT function with confidence
    bt_ratings, bt_std = compute_bt_with_confidence(df)

    tier_df = pd.DataFrame({
        "God": list(bt_ratings.keys()),
        "BT_Rating": [bt_ratings[g] for g in bt_ratings],
        "BT_SE": [bt_std[g] for g in bt_ratings],
        "WinRate": [winrates.get(g, 0) for g in bt_ratings]
    })

    tier_df = cluster_and_assign_tiers(tier_df, n_clusters=5)
    print_pretty_table_with_gap(tier_df, TIER_COLORS)

if __name__ == "__main__":
    main()
