from typing import Dict

import pandas as pd
import numpy as np
from analysis.visualization.visualization import get_conn  # Assuming this connects to your DB


# -------------------------------
# Data Loader
# -------------------------------
def load_data_list(include_engines: list) -> pd.DataFrame:
    """
    Load match data for all matches where both engines are in the given include_engines list.
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
# Bradley–Terry Model Estimation
# -------------------------------
def fit_bradley_terry(items: list, wins_ij: dict, matches_ij: dict, max_iter: int = 1000, tol: float = 1e-8) -> Dict[
    tuple, float]:
    """Fits the Bradley–Terry model to estimate ratings."""
    wins_total = {item: 0 for item in items}
    for (i, j), w in wins_ij.items():
        if i in wins_total: wins_total[i] += w
        if j not in wins_total: wins_total[j] = 0

    ratings = {item: 1.0 for item in items}

    for _ in range(max_iter):
        new_ratings = {}
        for i in items:
            denominator = 0.0
            for j in items:
                if i == j: continue

                key = tuple(sorted((i, j)))
                total_matches = matches_ij.get(key, 0)

                if total_matches > 0:
                    rating_sum = ratings.get(i, 0.0) + ratings.get(j, 0.0)
                    if rating_sum > 0:
                        denominator += total_matches / rating_sum

            if denominator > 0:
                new_ratings[i] = wins_total.get(i, 0) / denominator
            else:
                new_ratings[i] = ratings[i]

        diff = max(abs(new_ratings.get(i, 0) - ratings.get(i, 0)) for i in items)
        ratings = new_ratings
        if diff < tol:
            break

    # Normalize ratings
    valid_ratings = [r for item, r in ratings.items() if wins_total.get(item, 0) > 0]
    if not valid_ratings: return {item: 1500.0 for item in items}

    mean_rating = np.mean(valid_ratings)
    scale_factor = 1500 / mean_rating if mean_rating > 0 else 1.0

    return {i: val * scale_factor for i, val in ratings.items()}


# -------------------------------
# Main Execution
# -------------------------------

# 1. Configuration
include_engines = ["Fitos_4.6_Atium", "Fitos_5.1_Truthless",
                   "Fitos_6.3_Trick", "Fitos_7.2_Time", "Fitos_8.1_Cursed", "Fitos_9.4_Moth", "Fitos_10.5_Astro",
                   "Fitos_11.0_Hyperion", "Fitos_12.0_Never", "Paladini_1.4_Trigger", "Paladini_2.9_Apex",
                   "Paladini_3.0_Summit", "Paladini_4.1.1_Mystic", "Paladini_5.5.10_Velocity"]

# 2. Load Data
df = load_data_list(include_engines)
print("Engines included in the analysis:", sorted(set(df["Engine_G"]).union(df["Engine_B"])))

# 3. Prepare Pairwise Counts
items = sorted(set(zip(df["God_A"], df["Engine_G"])).union(set(zip(df["God_B"], df["Engine_B"]))))
matches_ij = {}
wins_ij = {}

for _, row in df.iterrows():
    item1 = (row["God_A"], row["Engine_G"])
    item2 = (row["God_B"], row["Engine_B"])

    # Increment match count for (i, j) and (j, i)
    matches_ij[(item1, item2)] = matches_ij.get((item1, item2), 0) + 1
    matches_ij[(item2, item1)] = matches_ij.get((item2, item1), 0) + 1

    # Increment win count for the winner
    if row["Result"] == 1:
        wins_ij[(item1, item2)] = wins_ij.get((item1, item2), 0) + 1
    elif row["Result"] == -1:
        wins_ij[(item2, item1)] = wins_ij.get((item2, item1), 0) + 1

# 4. Fit the Model (once, on the full dataset)
final_ratings = fit_bradley_terry(items, wins_ij, matches_ij)

# 5. Construct and Display Final Ranking Table
ranking_records = []
for item in items:
    god, engine = item

    # Get total matches and wins for the item
    total_wins = sum(wins_ij.get((item, j), 0) for j in items if item != j)
    total_matches = sum(matches_ij.get((item, j), 0) for j in items if item != j)

    win_rate = (total_wins / total_matches * 100) if total_matches > 0 else 0.0

    ranking_records.append({
        "God": god,
        "Engine": engine,
        "Matches": total_matches,
        "Wins": total_wins,
        "Win Rate (%)": win_rate,
        "Rating": final_ratings.get(item, 1500.0)  # Use the calculated rating
    })

ranking_df = pd.DataFrame(ranking_records)
ranking_df.sort_values(by="Rating", ascending=False, inplace=True)
ranking_df.reset_index(drop=True, inplace=True)

# 6. Report Results
print("\nRanking of God–Engine Pairs:")
print(ranking_df.to_string(index=False))
