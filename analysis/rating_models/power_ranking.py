from typing import Dict, List
import pandas as pd
import numpy as np
from analysis.visualization.visualization import get_conn


# -------------------------------
# Data Loader
# -------------------------------
def load_data_list(include_engines: list, conn) -> pd.DataFrame:
    """
    Load match data for all matches where both engines are in the given include_engines list.
    """
    engine_list_sql = ", ".join(f"'{engine}'" for engine in include_engines)
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
    df["Result"] = df["Result"].astype(int)
    return df


# -------------------------------
# Bradley–Terry Model Estimation
# -------------------------------
def fit_bradley_terry(items: List[tuple], wins_ij: Dict[tuple, int], matches_ij: Dict[tuple, int],
                      max_iter: int = 1000, tol: float = 1e-8) -> Dict[tuple, float]:
    """Fits the Bradley–Terry model to estimate ratings."""
    wins_total = {item: 0 for item in items}
    for (i, j), w in wins_ij.items():
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
                new_ratings[i] = ratings.get(i, 1.0)

        if not new_ratings: break

        diff = max(abs(new_ratings.get(i, 0) - ratings.get(i, 0)) for i in items)
        ratings = new_ratings
        if diff < tol:
            break

    valid_ratings = [r for r in ratings.values() if r > 0]
    if not valid_ratings: return {item: 1.0 for item in items}

    mean_rating = np.mean(valid_ratings)
    scale_factor = 1.0 / mean_rating if mean_rating > 0 else 1.0

    return {i: val * scale_factor for i, val in ratings.items()}


# -------------------------------
# Main Calculation and DB Population Function
# -------------------------------
def calculate_ratings(include_engines: List[str], save_to_db: bool = False, display:bool = False) -> pd.DataFrame:
    """
    Calculates God-Engine Elo ratings and optionally saves them to the database.

    Args:
        include_engines (List[str]): A list of engine names to include in the analysis.
        save_to_db (bool): If True, saves the results to the TB_ELO table.

    Returns:
        pd.DataFrame: A DataFrame containing the final rankings.
    """
    # Steps 1-5 (Data loading, calculation, and ranking) remain the same...
    # ... (code from the previous response for loading and calculations) ...
    # 1. Load Data
    conn = get_conn()
    try:
        df = load_data_list(include_engines, conn)
        print("Engines included in the analysis:", sorted(set(df["Engine_G"]).union(df["Engine_B"])))
    finally:
        conn.close()

    # 2. Prepare Pairwise Counts
    items = sorted(list(set(zip(df["God_A"], df["Engine_G"])).union(set(zip(df["God_B"], df["Engine_B"])))))
    matches_ij = {}
    wins_ij = {}

    for _, row in df.iterrows():
        item1 = (row["God_A"], row["Engine_G"])
        item2 = (row["God_B"], row["Engine_B"])
        key = tuple(sorted((item1, item2)))
        matches_ij[key] = matches_ij.get(key, 0) + 1
        if row["Result"] == 1:
            wins_ij[(item1, item2)] = wins_ij.get((item1, item2), 0) + 1
        elif row["Result"] == -1:
            wins_ij[(item2, item1)] = wins_ij.get((item2, item1), 0) + 1

    # 3. Fit the Model
    bt_ratings = fit_bradley_terry(items, wins_ij, matches_ij)

    # 4. Convert Bradley-Terry scores to Elo
    valid_bt_ratings = {item: score for item, score in bt_ratings.items() if score > 0}
    if valid_bt_ratings:
        min_bt_score = np.min(list(valid_bt_ratings.values()))
        K = -400 * np.log10(min_bt_score) if min_bt_score > 0 else 0
        elo_ratings = {item: (400 * np.log10(score) + K) if score > 0 else np.nan for item, score in bt_ratings.items()}
    else:
        elo_ratings = {item: 0.0 for item in items}

    # 5. Construct Final Ranking Table
    ranking_records = []
    for item in items:
        god, engine = item
        total_wins = sum(wins_ij.get((item, j), 0) for j in items if item != j)
        total_matches = sum(matches_ij.get(tuple(sorted((item, j))), 0) for j in items if item != j)
        win_rate = (total_wins / total_matches * 100) if total_matches > 0 else 0.0
        ranking_records.append({
            "God": god, "Engine": engine, "Matches": total_matches, "Wins": total_wins,
            "Win Rate (%)": win_rate, "Rating": bt_ratings.get(item, 0), "Elo": elo_ratings.get(item, 0.0)
        })

    ranking_df = pd.DataFrame(ranking_records)
    ranking_df.sort_values(by="Elo", ascending=False, inplace=True)
    ranking_df.reset_index(drop=True, inplace=True)

    if display:
        print("\n" + "=" * 80)
        print("Ranking of God–Engine Pairs")
        print("=" * 80)
        display_df = ranking_df.copy()
        display_df['Win Rate (%)'] = display_df['Win Rate (%)'].map('{:.2f}'.format)
        display_df['Rating'] = display_df['Rating'].map('{:.4f}'.format)
        display_df['Elo'] = display_df['Elo'].map('{:.2f}'.format)
        print(display_df.to_string())

    # 6. Save to Database if requested (REVISED LOGIC)
    if save_to_db:
        print("\nAttempting to save Elo ratings to the database...")
        conn = get_conn()
        try:
            cursor = conn.cursor()
            # Ensure the table exists with the correct schema
            create_table_query = """
            CREATE TABLE IF NOT EXISTS TB_ELO (
                "Engine" TEXT,
                "God"    TEXT,
                "Elo"    INTEGER NOT NULL,
                PRIMARY KEY("Engine", "God")
            )
            """
            cursor.execute(create_table_query)

            # Prepare the DataFrame for database insertion
            df_to_save = ranking_df[['Engine', 'God', 'Elo']].copy()
            df_to_save['Elo'] = df_to_save['Elo'].fillna(0).astype(int)

            # --- START: REVISED LOGIC ---
            # 1. Clear all existing data from the table. This is simpler and safer
            #    than trying to update specific rows.
            print("Clearing old data from TB_ELO...")
            cursor.execute("DELETE FROM TB_ELO;")

            # 2. Insert the new, freshly calculated data.
            print("Inserting new data into TB_ELO...")
            df_to_save.to_sql('TB_ELO', conn, if_exists='append', index=False)
            # --- END: REVISED LOGIC ---

            conn.commit()
            print(f"✅ Successfully saved {len(df_to_save)} records to TB_ELO.")

        except Exception as e:
            conn.rollback()
            print(f"❌ Database operation failed: {e}")
        finally:
            conn.close()

    return ranking_df


# -------------------------------
# Main Execution Block
# -------------------------------
if __name__ == "__main__":
    # Define the list of engines to analyze
    engines_to_analyze = [
        "Fitos_1.1_Ton", "Fitos_2.1_Scout", "Fitos_3.2_Life", "Fitos_4.6_Atium", "Fitos_5.1_Truthless",
        "Fitos_6.3_Trick", "Fitos_7.2_Time", "Fitos_8.1_Cursed", "Fitos_9.4_Moth", "Fitos_10.C5_Astro",
        "Fitos_11.0_Hyperion", "Fitos_12.0_Never", "Fitos_13.1_Legacy", "Fitos_14.8_Echo",
        "Paladini_1.4_Trigger", "Paladini_2.9_Apex",
        "Paladini_3.0_Summit", "Paladini_4.1.1_Mystic",
        "Paladini_5.5.40_Velocity", "Paladini_6.5.2_Prince",
        "Paladini_7.1_Lunar"
    ]

    # --- Example 1: Calculate ratings and save to the database ---
    print("--- Running analysis and saving to DB ---")
    final_rankings = calculate_ratings(include_engines=engines_to_analyze, save_to_db=True)

    # --- Example 2: Calculate ratings without saving to the database ---
    # print("\n\n--- Running analysis without saving to DB ---")
    # final_rankings_no_save = calculate_ratings(include_engines=engines_to_analyze, save_to_db=False