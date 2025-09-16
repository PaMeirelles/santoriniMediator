from typing import Dict, List

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
          AND (Time_G = 60 OR Time_G IS NULL)
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["Result"] = df["Result"].astype(int)
    return df


# -------------------------------
# Bradley–Terry Model Estimation
# -------------------------------
def fit_bradley_terry(items: List[tuple], wins_ij: Dict[tuple, int], matches_ij: Dict[tuple, int],
                      max_iter: int = 1000, tol: float = 1e-8) -> Dict[tuple, float]:
    """Fits the Bradley–Terry model to estimate ratings."""
    wins_total = {item: 0 for item in items}
    for (i, _), w in wins_ij.items():
        if i in wins_total:
            wins_total[i] += w

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
                    rating_sum = ratings.get(i, 1.0) + ratings.get(j, 1.0)
                    if rating_sum > 0:
                        denominator += total_matches / rating_sum

            if denominator > 0:
                new_ratings[i] = wins_total.get(i, 0) / denominator
            else:
                new_ratings[i] = ratings.get(i, 1.0)  # Keep old rating if no matches

        if not new_ratings: break

        diff = max(abs(new_ratings.get(i, 0) - ratings.get(i, 0)) for i in items)
        ratings = new_ratings
        if diff < tol:
            break

    # Normalize ratings so that the average is meaningful
    valid_ratings = [r for r in ratings.values() if r > 0]
    if not valid_ratings: return {item: 1.0 for item in items}

    mean_rating = np.mean(valid_ratings)
    scale_factor = 1.0 / mean_rating if mean_rating > 0 else 1.0

    return {i: val * scale_factor for i, val in ratings.items()}


# -------------------------------
# Main Execution
# -------------------------------

# 1. Configuration
include_engines = ["Fitos_1.1_Ton", "Fitos_2.1_Scout", "Fitos_3.2_Life", "Fitos_4.6_Atium", "Fitos_5.1_Truthless",
                   "Fitos_6.3_Trick", "Fitos_7.2_Time", "Fitos_8.1_Cursed", "Fitos_9.4_Moth", "Fitos_10.5_Astro",
                   "Fitos_11.0_Hyperion", "Fitos_12.0_Never", "Fitos_13.1_Legacy", "Fitos_14.8_Echo",
                   "Paladini_1.4_Trigger", "Paladini_2.9_Apex",
                   "Paladini_3.0_Summit", "Paladini_4.1.1_Mystic",
                   "Paladini_5.5.40_Velocity"
                   ]

# 2. Load Data
df = load_data_list(include_engines)
print("Engines included in the analysis:", sorted(set(df["Engine_G"]).union(df["Engine_B"])))

# 3. Prepare Pairwise Counts
items = sorted(list(set(zip(df["God_A"], df["Engine_G"])).union(set(zip(df["God_B"], df["Engine_B"])))))
matches_ij = {}
wins_ij = {}

for _, row in df.iterrows():
    item1 = (row["God_A"], row["Engine_G"])
    item2 = (row["God_B"], row["Engine_B"])

    # Increment match count using a sorted, canonical key to count each match once
    key = tuple(sorted((item1, item2)))
    matches_ij[key] = matches_ij.get(key, 0) + 1

    # Increment win count for the winner
    if row["Result"] == 1:
        wins_ij[(item1, item2)] = wins_ij.get((item1, item2), 0) + 1
    elif row["Result"] == -1:
        wins_ij[(item2, item1)] = wins_ij.get((item2, item1), 0) + 1

# 4. Fit the Model
bt_ratings = fit_bradley_terry(items, wins_ij, matches_ij)

# 5. Convert Bradley-Terry scores to Elo
# Filter out items with a non-positive BT rating for stable log calculation
valid_bt_ratings = {item: score for item, score in bt_ratings.items() if score > 0}

if valid_bt_ratings:
    valid_scores = np.array(list(valid_bt_ratings.values()))

    # Find the minimum positive BT score to set the base for Elo
    min_bt_score = np.min(valid_scores)

    # Calculate offset K to anchor the lowest rating at 0 Elo
    # The formula is: Elo = 400 * log10(BT_Score) + K
    # For the lowest score: 0 = 400 * log10(min_bt_score) + K
    # Thus, K = -400 * log10(min_bt_score)
    K = -400 * np.log10(min_bt_score)

    elo_ratings = {}
    for item, bt_score in bt_ratings.items():
        if bt_score > 0:
            elo_ratings[item] = 400 * np.log10(bt_score) + K
        else:
            elo_ratings[item] = np.nan  # Use NaN for items with 0 score (e.g., 0 wins)
else:
    elo_ratings = {item: 0.0 for item in items} # Default to 0 if no valid ratings

# 6. Construct and Display Final Ranking Table
ranking_records = []
for item in items:
    god, engine = item

    # Get total matches and wins for the item
    total_wins = sum(wins_ij.get((item, j), 0) for j in items if item != j)
    total_matches = sum(matches_ij.get(tuple(sorted((item, j))), 0) for j in items if item != j)

    win_rate = (total_wins / total_matches * 100) if total_matches > 0 else 0.0

    ranking_records.append({
        "God": god,
        "Engine": engine,
        "Matches": total_matches,
        "Wins": total_wins,
        "Win Rate (%)": win_rate,
        "Rating": bt_ratings.get(item, 0),
        "Elo": elo_ratings.get(item, 0.0) # Use 0.0 as default for consistency
    })

ranking_df = pd.DataFrame(ranking_records)
ranking_df.sort_values(by="Elo", ascending=False, inplace=True)
ranking_df.reset_index(drop=True, inplace=True)

# Format for better readability
ranking_df['Win Rate (%)'] = ranking_df['Win Rate (%)'].map('{:.2f}'.format)
ranking_df['Rating'] = ranking_df['Rating'].map('{:.4f}'.format)
ranking_df['Elo'] = ranking_df['Elo'].map('{:.2f}'.format)

# 7. Report Results and Save to CSV
print("\n" + "=" * 80)
print("Ranking of God–Engine Pairs")
print("=" * 80)
print(ranking_df.to_string())

# --- Save the God-Engine ranking table to a CSV file ---
ranking_df.to_csv('../../data/god_engine_rankings.csv', index=False)
print("\n✅ God-Engine rankings saved to 'god_engine_rankings.csv'")


# 8. Create, Display, and Save Engine-level Elo Table
# Convert Elo column back to numeric for calculation, handling potential NaNs
ranking_df['Elo'] = pd.to_numeric(ranking_df['Elo'], errors='coerce')

engine_elo_df = ranking_df.groupby('Engine')['Elo'].mean().reset_index()
engine_elo_df.rename(columns={'Elo': 'Average Elo'}, inplace=True)
engine_elo_df.sort_values(by="Average Elo", ascending=False, inplace=True)
engine_elo_df.reset_index(drop=True, inplace=True)

# Format for better readability
engine_elo_df['Average Elo'] = engine_elo_df['Average Elo'].map('{:.2f}'.format)

print("\n" + "=" * 80)
print("Ranking of Engines by Average Elo")
print("=" * 80)
print(engine_elo_df.to_string(index=False))

# --- Save the Engine-level Elo table to a CSV file ---
engine_elo_df.to_csv('../../data/engine_average_elo.csv', index=False)
print("\n✅ Engine average Elo rankings saved to 'engine_average_elo.csv'")