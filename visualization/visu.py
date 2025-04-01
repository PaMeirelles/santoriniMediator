import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans

# -------------------------
# 1. Parse the CSV data
# -------------------------
df = pd.read_csv("../match_results.csv")
df = df[df["God_A"] != "God_A"]
df["Result"] = df["Result"].astype(int)

# -------------------------
# 2. Create the matchup heatmap matrix
# -------------------------
gods = sorted(set(df["God_A"]).union(set(df["God_B"])))
matchup_matrix = pd.DataFrame(0, index=gods, columns=gods)

for _, row in df.iterrows():
    ga, gb, r = row["God_A"], row["God_B"], row["Result"]
    matchup_matrix.loc[ga, gb] += r
    matchup_matrix.loc[gb, ga] -= r

fig, ax = plt.subplots(figsize=(8, 6))
cax = ax.matshow(matchup_matrix, cmap="coolwarm")
fig.colorbar(cax)
ax.set_xticks(np.arange(len(gods)))
ax.set_xticklabels(gods, rotation=90, color='white')
ax.set_yticks(np.arange(len(gods)))
ax.set_yticklabels(gods, color='white')
for i in range(len(gods)):
    for j in range(len(gods)):
        ax.text(j, i, f"{matchup_matrix.iloc[i, j]:+d}",
                ha="center", va="center", color="black", fontsize=9)
ax.set_title("Gods Matchup Heatmap", pad=20, color='white')
fig.patch.set_facecolor('black')
ax.set_facecolor('black')
plt.tight_layout()
plt.show()

# -------------------------
# 3. Compute win rates
# -------------------------
win_counts = {god: 0 for god in gods}
loss_counts = {god: 0 for god in gods}
for _, row in df.iterrows():
    ga, gb, r = row["God_A"], row["God_B"], row["Result"]
    if r == 1:
        win_counts[ga] += 1
        loss_counts[gb] += 1
    elif r == -1:
        win_counts[gb] += 1
        loss_counts[ga] += 1

winrates = {god: win_counts[god] / (win_counts[god] + loss_counts[god])
            if (win_counts[god] + loss_counts[god]) > 0 else 0
            for god in gods}

# -------------------------
# 4. Clustering to Tiers S-D
# -------------------------
X = np.array([[winrates[god]] for god in gods])
kmeans = KMeans(n_clusters=5, random_state=0).fit(X)
labels = kmeans.labels_

tier_df = pd.DataFrame({
    "God": gods,
    "WinRate": [winrates[god] for god in gods],
    "Cluster": labels
})

tier_labels = ['S', 'A', 'B', 'C', 'D']
cluster_order = tier_df.groupby("Cluster")["WinRate"].mean().sort_values(ascending=False).index
cluster_to_tier = {cluster: tier_labels[i] for i, cluster in enumerate(cluster_order)}
tier_df["Tier"] = tier_df["Cluster"].map(cluster_to_tier)

# Order: S > A > ... > D; within tier: descending winrate
tier_df["TierRank"] = tier_df["Tier"].map({t: i for i, t in enumerate(tier_labels)})
tier_df.sort_values(by=["TierRank", "WinRate"], ascending=[False, True], inplace=True)
tier_df.drop(columns="TierRank", inplace=True)

# -------------------------
# 5. Tier Plot (black bg, proper sorting, fixed text)
# -------------------------
tier_colors = {
    'S': '#FF6C6C',
    'A': '#FFBC7D',
    'B': '#FFE780',
    'C': '#FFFFA0',
    'D': '#B8FF84',
}

fig, ax = plt.subplots(figsize=(10, 6))
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

# No inverting – top = best
tier_df = tier_df.reset_index(drop=True)
bars = ax.barh(tier_df.index, tier_df["WinRate"],
               color=[tier_colors[row.Tier] for row in tier_df.itertuples()])

ax.set_yticks(tier_df.index)
ax.set_yticklabels(tier_df["God"], fontsize=10, color='white')
ax.set_xlabel("Win Rate", color='white')
ax.set_title("Gods Tier List", color='white', pad=20)

# Annotations: fixed font size, white text, limit offset
for i, row in tier_df.iterrows():
    text = f"{row.Tier} ({row.WinRate*100:.1f}%)"
    ax.text(min(row.WinRate + 0.01, 0.98), i, text, va="center",
            fontsize=9, color='white')

ax.tick_params(colors='white')
plt.tight_layout()
plt.show()

# --- Tier Plot with God Icons ---
import os
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patches as patches

# tier_df has ["God", "WinRate", "Cluster", "Tier"] with Tier in {S, A, B, C, D}.

tier_order = ["S", "A", "B", "C", "D"]
tier_bg_colors = {
    "S": "#FF6C6C",
    "A": "#FFBC7D",
    "B": "#FFE780",
    "C": "#FFFFA0",
    "D": "#B8FF84",
}

# Layout parameters
row_height = 1.0       # each tier row is 1 unit high
gap_height = 0.02      # thin black stripe height between tiers
label_width = 1.0      # width of the colored tier label cell
vertical_strip_width = 0.02  # thin black strip between the label cell and the icons
n_tiers = len(tier_order)

# Total vertical space = sum of row heights + black stripes
total_height = n_tiers * row_height + (n_tiers - 1) * gap_height
# Make total_width = total_height so the data area is a perfect square
total_width = total_height

fig, ax = plt.subplots(figsize=(9, 9))  # a square figure
fig.patch.set_facecolor("#2c2c2c")      # dark gray figure background
ax.set_facecolor("#2c2c2c")             # dark gray axes background

ax.set_xlim(0, total_width)
ax.set_ylim(0, total_height)
ax.set_aspect("equal", adjustable="box")
ax.axis("off")

# Start from the top
y_current = total_height

for i, tier in enumerate(tier_order):
    # Coordinates for this tier row
    y_top = y_current
    y_bottom = y_top - row_height

    # 1) Draw the colored tier label cell (x=0..label_width)
    rect = patches.Rectangle(
        (0, y_bottom),
        label_width,
        row_height,
        facecolor=tier_bg_colors[tier],
        edgecolor=None
    )
    ax.add_patch(rect)

    # Center the tier letter in black font
    ax.text(
        label_width / 2,
        (y_bottom + y_top) / 2,
        tier,
        color="black",
        fontsize=30,
        ha="center",
        va="center"
    )

    # 2) Thin black vertical strip after the label cell
    #    from x=label_width..(label_width + vertical_strip_width)
    strip_rect = patches.Rectangle(
        (label_width, y_bottom),
        vertical_strip_width,
        row_height,
        facecolor="black",
        edgecolor=None
    )
    ax.add_patch(strip_rect)

    # 3) Place icons (1×1 each) immediately to the right of that black strip
    x_current = label_width + vertical_strip_width
    icon_size = row_height  # square bounding box

    # Sort gods in descending WinRate
    subset = tier_df[tier_df["Tier"] == tier].sort_values("WinRate", ascending=False)
    gods_in_tier = subset["God"].tolist()

    for god in gods_in_tier:
        # Find the matching image
        image_path = None
        for ext in (".png", ".jpg", ".jpeg"):
            path = f"god_icons/{god}{ext}"
            if os.path.exists(path):
                image_path = path
                break
        if not image_path:
            print(f"Missing icon for {god}")
            continue

        left = x_current
        right = left + icon_size
        ax.imshow(
            mpimg.imread(image_path),
            extent=(left, right, y_bottom, y_top),
            aspect="auto"
        )
        x_current += icon_size  # no gap between icons

    # 4) Thin black horizontal stripe between tiers (except the last one)
    y_current = y_bottom
    if i < n_tiers - 1:
        stripe_bottom = y_current - gap_height
        stripe_rect = patches.Rectangle(
            (0, stripe_bottom),
            total_width,
            gap_height,
            facecolor="black",
            edgecolor=None
        )
        ax.add_patch(stripe_rect)
        y_current = stripe_bottom

plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
plt.show()


