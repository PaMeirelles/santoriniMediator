#!/usr/bin/env python3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from collections import defaultdict
import os
import matplotlib.image as mpimg
import matplotlib.patches as patches

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

# -------------------------
# 1. Read from SQLite DB
# -------------------------
DB_PATH = "../data/matches.db"
ENGINE_NAME = "Fitos_2.1_Scout"

conn = sqlite3.connect(DB_PATH)
query = f"""
SELECT GOD_G AS God_A, God_B AS God_B, result AS Result
FROM TB_MATCHES
WHERE Engine_G = '{ENGINE_NAME}' AND Engine_B = '{ENGINE_NAME}'
"""

df = pd.read_sql_query(query, conn)
conn.close()

df["Result"] = df["Result"].astype(int)
gods = sorted(set(df["God_A"]).union(set(df["God_B"])))


# -------------------------
# 2. Compute Win Rates & Matchup WR
# -------------------------
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

winrates = {g: win_counts[g] / (win_counts[g] + loss_counts[g]) if (win_counts[g] + loss_counts[g]) > 0 else 0 for g in gods}
matchup_wr = matchup_wins.divide(matchup_matches).fillna(0)

for i in range(len(gods)):
    matchup_wr.iloc[i, i] = np.nan
masked_wr = np.ma.masked_invalid(matchup_wr.values)
cmap = plt.get_cmap("RdYlGn")
cmap.set_bad(color='gray')

fig, ax = plt.subplots(figsize=(10, 8))
cax = ax.imshow(masked_wr, cmap=cmap, vmin=0, vmax=1)
fig.colorbar(cax)
ax.set_xticks(np.arange(len(gods)))
ax.set_xticklabels(gods, rotation=90, color='white')
ax.set_yticks(np.arange(len(gods)))
ax.set_yticklabels(gods, color='white')
ax.set_title("Matchup Win Rate Heatmap", color='white', pad=20)
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

for i in range(len(gods)):
    for j in range(len(gods)):
        if i != j:
            wr_value = matchup_wr.iloc[i, j]
            ax.text(j, i, f"{wr_value*100:.0f}%", ha="center", va="center", color="black", fontsize=8)
plt.tight_layout()
plt.show()

# -------------------------
# 4. Compute Bradley-Terry Ratings
# -------------------------
def compute_bt_ratings(df, gods, max_iter=1000, tol=1e-5):
    wins_bt = defaultdict(lambda: defaultdict(int))
    matches_bt = defaultdict(lambda: defaultdict(int))
    for _, row in df.iterrows():
        ga, gb, r = row["God_A"], row["God_B"], row["Result"]
        matches_bt[ga][gb] += 1
        matches_bt[gb][ga] += 1
        if r == 1:
            wins_bt[ga][gb] += 1
        elif r == -1:
            wins_bt[gb][ga] += 1
    ratings = {g: 1.0 for g in gods}
    for _ in range(max_iter):
        new_ratings = {}
        max_change = 0.0
        for g in gods:
            total_wins = sum(wins_bt[g].values())
            denom = sum(matches_bt[g][j] / (ratings[g] + ratings[j]) for j in matches_bt[g])
            new_rating = ratings[g] if denom == 0 else total_wins / denom
            new_ratings[g] = new_rating
            max_change = max(max_change, abs(new_rating - ratings[g]))
        ratings = new_ratings
        if max_change < tol:
            break
    return ratings

bt_ratings = compute_bt_ratings(df, gods)
min_bt = min(bt_ratings.values())
bt_ratings_norm = {g: bt_ratings[g] - min_bt for g in gods}

# -------------------------
# 5. Create Tier Table
# -------------------------
tier_df = pd.DataFrame({
    "God": gods,
    "WinRate": [winrates[g] for g in gods],
    "BT_Rating": [bt_ratings_norm[g] for g in gods]
})

kmeans = KMeans(n_clusters=5, random_state=0).fit(tier_df[["BT_Rating"]])
tier_labels = ['S', 'A', 'B', 'C', 'D']
cluster_order = tier_df.groupby(kmeans.labels_)["BT_Rating"].mean().sort_values(ascending=False).index
cluster_to_tier = {cluster: tier_labels[i] for i, cluster in enumerate(cluster_order)}
tier_df["Cluster"] = kmeans.labels_
tier_df["Tier"] = tier_df["Cluster"].map(cluster_to_tier)
tier_order_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
tier_df["TierRank"] = tier_df["Tier"].map(tier_order_map)
tier_df = tier_df.sort_values(by=["TierRank", "WinRate"], ascending=[False, False]).reset_index(drop=True)
bt_ratings_list = tier_df["BT_Rating"].tolist()
bt_gap = [round(bt_ratings_list[i] - bt_ratings_list[i+1], 2) for i in range(len(bt_ratings_list)-1)] + [0.00]
tier_df["BT Gap"] = bt_gap



# -------------------------
# 6. Pretty Table Print
# -------------------------
def hex_to_rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))

def ansi_color_text(text, hex_color):
    r, g, b = hex_to_rgb(hex_color)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

def print_pretty_table_with_gap(df, tier_colors):
    headers = ["God", "Win Rate", "BT Rating", "BT Gap", "Tier"]
    data = []
    for _, row in df.iterrows():
        data.append([
            row["God"],
            f"{row['WinRate']*100:.1f}%",
            f"{row['BT_Rating']:.2f}",
            f"{row['BT Gap']:.2f}",
            row["Tier"]
        ])
    col_widths = [max(len(str(cell)) for cell in [header] + [row[i] for row in data]) for i, header in enumerate(headers)]
    sep = "+" + "+".join("-"*(w+2) for w in col_widths) + "+"
    print(sep)
    print("| " + " | ".join(header.ljust(col_widths[i]) for i, header in enumerate(headers)) + " |")
    print(sep)
    for row in data:
        tier_col = ansi_color_text(row[4].ljust(col_widths[4]), tier_colors[row[4]])
        parts = row[:4] + [tier_col]
        print("| " + " | ".join(str(parts[i]).ljust(col_widths[i]) for i in range(5)) + " |")
    print(sep)

tier_colors = {
    'S': '#FF6C6C',
    'A': '#FFBC7D',
    'B': '#FFE780',
    'C': '#FFFFA0',
    'D': '#B8FF84'
}

print_pretty_table_with_gap(tier_df, tier_colors)

# -------------------------
# 7. Icon Tier List Plot
# -------------------------
def plot_tier_icons(df):
    tier_order = ["S", "A", "B", "C", "D"]

    # Basic layout parameters
    row_height = 1.0
    gap_height = 0.02
    label_width = 1.0
    vertical_strip_width = 0.02
    icon_width = 1.0  # each icon occupies '1.0' width in that tier's row

    # Find how many icons per tier and track the widest row
    max_width = 0
    for tier in tier_order:
        subset = df[df["Tier"] == tier]
        n_icons = len(subset)
        row_width = label_width + vertical_strip_width + n_icons * icon_width
        max_width = max(max_width, row_width)

    # Compute total height: one row per tier + small gaps
    total_height = len(tier_order) * row_height + (len(tier_order) - 1) * gap_height

    # Make the figure a bit bigger than our raw “width × height”
    fig, ax = plt.subplots(figsize=(max_width * 1.2, total_height * 1.2))
    fig.patch.set_facecolor("#2c2c2c")
    ax.set_facecolor("#2c2c2c")

    ax.set_xlim(0, max_width)
    ax.set_ylim(0, total_height)
    # Use aspect="auto" so the x- and y-scales can differ (prevents squashing)
    ax.set_aspect("auto")
    ax.axis("off")

    # Start from top row downward
    y_current = total_height
    for i, tier in enumerate(tier_order):
        y_top = y_current
        y_bottom = y_top - row_height

        # Tier label box
        ax.add_patch(patches.Rectangle((0, y_bottom), label_width, row_height,
                                       facecolor=tier_colors[tier]))
        ax.text(label_width / 2, (y_bottom + y_top) / 2, tier, color="black",
                fontsize=30, ha="center", va="center")

        # Narrow black divider patch
        ax.add_patch(patches.Rectangle((label_width, y_bottom),
                                       vertical_strip_width, row_height,
                                       facecolor="black"))

        # Place icons side by side
        subset = df[df["Tier"] == tier].sort_values("WinRate", ascending=False)
        x_current = label_width + vertical_strip_width
        for god in subset["God"]:
            # find actual path
            image_path = None
            for ext in (".png", ".jpg", ".jpeg"):
                candidate = f"god_icons/{god}{ext}"
                if os.path.exists(candidate):
                    image_path = candidate
                    break
            if not image_path:
                print(f"Missing icon for {god}")
                continue

            # Draw icon in the [x_current..x_current+icon_width] region
            ax.imshow(mpimg.imread(image_path),
                      extent=(x_current, x_current + icon_width,
                              y_bottom, y_top))
            x_current += icon_width

        # Add small gap after the row (except the last one)
        if i < len(tier_order) - 1:
            y_current = y_bottom - gap_height
            ax.add_patch(patches.Rectangle((0, y_current), max_width, gap_height, facecolor="black"))
        else:
            y_current = y_bottom

    # Final layout
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.show()


plot_tier_icons(tier_df)