import pandas as pd
import numpy as np
from analysis.visualization import get_conn  # for DB connection
from scipy.stats import scoreatpercentile


# -------------------------------
# Modified Data Loader
# -------------------------------
def load_data_list(include_engines: list) -> pd.DataFrame:
    """
    Load match data for all matches where both engines are in the given include_engines list.

    The query selects matches where Engine_G AND Engine_B are in the provided engine list.
    """
    engine_list_sql = ", ".join(f"'{engine}'" for engine in include_engines)
    conn = get_conn()
    query = f"""
        SELECT Id,
               GOD_G AS God_A,
               GOD_B AS God_B,
               result AS Result,
               Engine_G,
               Engine_B,
               Starting_pos
        FROM TB_MATCHES
        WHERE Engine_G IN ({engine_list_sql})
          AND Engine_B IN ({engine_list_sql})
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["Result"] = df["Result"].astype(int)
    return df


# -------------------------------
# Configuration
# -------------------------------
# List of engines to include.
include_engines = ["Fitos_4.6_Atium", "Fitos_5.1_Truthless", "Fitos_6.3_Trick",
                   "Fitos_7.2_Time", "Fitos_8.1_Cursed", "Fitos_9.4_Moth", "Fitos_10.5_Astro", "Fitos_11.0_Hyperion"]

# Number of bootstrap iterations for uncertainty quantification
n_bootstrap = 100

# -------------------------------
# Load Data
# -------------------------------
df = load_data_list(include_engines)
all_engines = sorted(set(df["Engine_G"]).union(df["Engine_B"]))
print("Engines included in the analysis:", all_engines)

# -------------------------------
# Build Raw Performance Records
# -------------------------------
# Create records per (god, engine) pair from the match data.
records = {}  # keys: (god, engine), values: dict with Matches and Wins
for idx, row in df.iterrows():
    # For side 1: God_A and Engine_G; win if Result==1.
    item1 = (row["God_A"], row["Engine_G"])
    result1 = 1 if row["Result"] == 1 else 0
    if item1 not in records:
        records[item1] = {"Matches": 0, "Wins": 0}
    records[item1]["Matches"] += 1
    records[item1]["Wins"] += result1

    # For side 2: God_B and Engine_B; win if Result==-1.
    item2 = (row["God_B"], row["Engine_B"])
    result2 = 1 if row["Result"] == -1 else 0
    if item2 not in records:
        records[item2] = {"Matches": 0, "Wins": 0}
    records[item2]["Matches"] += 1
    records[item2]["Wins"] += result2

# Convert raw records to a DataFrame.
raw_records = []
for (god, engine), rec in records.items():
    win_rate = rec["Wins"] / rec["Matches"]
    raw_records.append({
        "God": god,
        "Engine": engine,
        "Matches": rec["Matches"],
        "Wins": rec["Wins"],
        "Win Rate (%)": win_rate * 100
    })
raw_df = pd.DataFrame(raw_records)

# -------------------------------
# Prepare Pairwise Counts for Bradley–Terry
# -------------------------------
# We build counts of how many times item i faced item j, and how many wins were recorded.
matches_ij = {}
wins_ij = {}
items = sorted(records.keys())
for idx, row in df.iterrows():
    item1 = (row["God_A"], row["Engine_G"])
    item2 = (row["God_B"], row["Engine_B"])
    # Update (item1, item2)
    matches_ij[(item1, item2)] = matches_ij.get((item1, item2), 0) + 1
    if row["Result"] == 1:
        wins_ij[(item1, item2)] = wins_ij.get((item1, item2), 0) + 1
    else:
        wins_ij[(item1, item2)] = wins_ij.get((item1, item2), 0)
    # And for reverse matchup (item2, item1)
    matches_ij[(item2, item1)] = matches_ij.get((item2, item1), 0) + 1
    if row["Result"] == -1:
        wins_ij[(item2, item1)] = wins_ij.get((item2, item1), 0) + 1
    else:
        wins_ij[(item2, item1)] = wins_ij.get((item2, item1), 0)


# -------------------------------
# Bradley–Terry Model Estimation Function
# -------------------------------
def fit_bradley_terry(df_matches, items, max_iter=1000, tol=1e-8):
    """
    Fit the Bradley–Terry model on the given match data (subset in df_matches).
    Returns a dictionary mapping each item (god, engine) to its normalized rating.
    """
    # Build pairwise counts for this bootstrap sample.
    matches_ij_bs = {}
    wins_ij_bs = {}
    for idx, row in df_matches.iterrows():
        item1 = (row["God_A"], row["Engine_G"])
        item2 = (row["God_B"], row["Engine_B"])
        matches_ij_bs[(item1, item2)] = matches_ij_bs.get((item1, item2), 0) + 1
        if row["Result"] == 1:
            wins_ij_bs[(item1, item2)] = wins_ij_bs.get((item1, item2), 0) + 1
        else:
            wins_ij_bs[(item1, item2)] = wins_ij_bs.get((item1, item2), 0)

        matches_ij_bs[(item2, item1)] = matches_ij_bs.get((item2, item1), 0) + 1
        if row["Result"] == -1:
            wins_ij_bs[(item2, item1)] = wins_ij_bs.get((item2, item1), 0) + 1
        else:
            wins_ij_bs[(item2, item1)] = wins_ij_bs.get((item2, item1), 0)

    # Compute total wins per item
    wins_total_bs = {item: 0 for item in items}
    for (i, j), w in wins_ij_bs.items():
        wins_total_bs[i] += w

    # Initialize ratings.
    r = {item: 1.0 for item in items}
    for it in range(max_iter):
        r_new = {}
        for i in items:
            denom = 0.0
            for j in items:
                if i == j:
                    continue
                n_ij = matches_ij_bs.get((i, j), 0)
                if n_ij > 0:
                    denom += n_ij / (r[i] + r[j])
            if denom > 0:
                r_new[i] = wins_total_bs[i] / denom
            else:
                r_new[i] = r[i]
        diff = max(abs(r_new[i] - r[i]) for i in items)
        r = r_new
        if diff < tol:
            break
    # Normalize ratings (for easier interpretation; here we set mean rating to 1500).
    mean_rating = np.mean(list(r.values()))
    r_norm = {i: (val / mean_rating) * 1500 for i, val in r.items()}
    return r_norm


# -------------------------------
# Bootstrap for Uncertainty
# -------------------------------
# We perform bootstrap resampling of the matches from df to obtain distributions of ratings.
bootstrap_ratings = {item: [] for item in items}
n = len(df)
for b in range(n_bootstrap):
    # Sample with replacement from the match DataFrame.
    df_bs = df.sample(n=n, replace=True)
    r_bs = fit_bradley_terry(df_bs, items)
    for item in items:
        bootstrap_ratings[item].append(r_bs[item])

# -------------------------------
# Construct Final Ranking Table with Uncertainty Estimates
# -------------------------------
ranking_records = []
for item in items:
    god, engine = item
    # Get raw record for this pair, if any.
    rec = raw_df[(raw_df["God"] == god) & (raw_df["Engine"] == engine)]
    if not rec.empty:
        matches = rec["Matches"].iloc[0]
        wins = rec["Wins"].iloc[0]
        win_rate = rec["Win Rate (%)"].iloc[0]
    else:
        matches, wins, win_rate = 0, 0, 0.0
    ratings_bs = bootstrap_ratings[item]
    rating_mean = np.mean(ratings_bs)
    rating_lb = scoreatpercentile(ratings_bs, 2.5)
    rating_ub = scoreatpercentile(ratings_bs, 97.5)
    ranking_records.append({
        "God": god,
        "Engine": engine,
        "Matches": matches,
        "Wins": wins,
        "Win Rate (%)": win_rate,
        "Rating Mean": rating_mean,
        "Rating 2.5%": rating_lb,
        "Rating 97.5%": rating_ub
    })
ranking_df = pd.DataFrame(ranking_records)
ranking_df.sort_values(by="Rating Mean", ascending=False, inplace=True)
ranking_df.reset_index(drop=True, inplace=True)

# -------------------------------
# Report Results
# -------------------------------
print("\nRanking of God–Engine Pairs (with uncertainty from bootstrap):")
print(ranking_df.to_string(index=False))
