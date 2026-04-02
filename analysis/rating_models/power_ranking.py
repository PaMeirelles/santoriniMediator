from typing import Dict, List, Tuple, Optional
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
def fit_bradley_terry(
        items: List[Tuple],
        wins_ij: Dict[Tuple, int],
        matches_ij: Dict[Tuple, int],
        max_iter: int = 1000,
        tol: float = 1e-6,
        log_interval: int = 100,
        initial_ratings: Optional[Dict[Tuple, float]] = None  # <-- MODIFIED
) -> Dict[Tuple, float]:
    """
    Fits the Bradley–Terry model to estimate ratings.

    Args:
        items: A list of all items to be rated.
        wins_ij: A dictionary where keys are (i, j) tuples and values are the number of times i won against j.
        matches_ij: A dictionary where keys are sorted (i, j) tuples and values are total matches between i and j.
        max_iter: The maximum number of iterations to perform.
        tol: The tolerance for convergence.
        log_interval: Print progress every `log_interval` iterations.
        initial_ratings: An optional dictionary of ratings to use as a starting point (warm start).
    """
    wins_total = {item: 0 for item in items}
    for (i, j), w in wins_ij.items():
        if i in wins_total:
            wins_total[i] += w

    # --- MODIFIED: Conditional initialization for warm start ---
    if initial_ratings:
        # Calculate the average of existing ratings to use as a sensible default for new items
        average_rating = np.mean(list(initial_ratings.values())) if initial_ratings else 1.0

        ratings = {item: initial_ratings.get(item, average_rating) for item in items}

        # Optional: Add a more informative print statement
        num_new = len(items) - len(initial_ratings)
        print("💡 Model warm-started with initial ratings.")
        if num_new > 0:
            print(f"   Initialized {num_new} new item(s) with the average rating of {average_rating:.2f}.")

    else:
        ratings = {item: 1.0 for item in items}

    for iter_num in range(max_iter):
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
        if not new_ratings:
            print("Warning: No new ratings could be calculated. Stopping.")
            break
        diff = max(abs(new_ratings.get(i, 0) - ratings.get(i, 0)) for i in items)
        ratings = new_ratings
        if log_interval and (iter_num + 1) % log_interval == 0:
            print(f"Iteration {iter_num + 1}/{max_iter}: Max rating change = {diff:.3e}")
        if diff < tol:
            print(f"✅ Converged after {iter_num + 1} iterations.")
            break
    else:
        print(f"⚠️ Warning: Model did not converge after {max_iter} iterations.")

    valid_ratings = [r for r in ratings.values() if r > 0]
    if not valid_ratings: return {item: 1.0 for item in items}
    mean_rating = np.mean(valid_ratings)
    scale_factor = 1.0 / mean_rating if mean_rating > 0 else 1.0
    return {i: val * scale_factor for i, val in ratings.items()}


# -------------------------------
# Main Calculation and DB Population Function
# -------------------------------
def calculate_ratings(include_engines: List[str], save_to_db: bool = False, display: bool = False,
                      warm_start_from_db: bool = False) -> pd.DataFrame:
    """
    Calculates God-Engine Elo ratings and optionally saves them to the database.

    Args:
        include_engines (List[str]): A list of engine names to include in the analysis.
        save_to_db (bool): If True, saves the results to the TB_ELO table.
        display (bool): If True, prints the final ranking table to the console.
        warm_start_from_db (bool): If True, loads existing ratings from TB_ELO to use as a starting point.
    """
    # 1. Load Data
    conn = get_conn()
    try:
        df = load_data_list(include_engines, conn)
        print("Engines included in the analysis:", sorted(set(df["Engine_G"]).union(df["Engine_B"])))
    finally:
        conn.close()

    # 2. Prepare Pairwise Counts
    items = sorted(list(set(zip(df["God_A"], df["Engine_G"])).union(set(zip(df["God_B"], df["Engine_B"])))))
    df['item1'] = list(zip(df['God_A'], df['Engine_G']))
    df['item2'] = list(zip(df['God_B'], df['Engine_B']))
    df['key'] = df.apply(lambda row: tuple(sorted((row['item1'], row['item2']))), axis=1)
    matches_ij = df['key'].value_counts().to_dict()
    wins_df = df[df['Result'] != 0].copy()
    wins_df['winner'] = np.where(wins_df['Result'] == 1, wins_df['item1'], wins_df['item2'])
    wins_df['loser'] = np.where(wins_df['Result'] == 1, wins_df['item2'], wins_df['item1'])
    wins_ij = wins_df.groupby(['winner', 'loser']).size().to_dict()

    # --- NEW: Logic for Warm Start ---
    initial_bt_ratings = None
    if warm_start_from_db:
        print("\nAttempting to warm-start from database ratings...")
        conn = get_conn()
        try:
            # Check if table exists before trying to read
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_ELO';")
            if cursor.fetchone():
                elo_df = pd.read_sql_query("SELECT God, Engine, Elo FROM TB_ELO", conn)
                if not elo_df.empty:
                    # Convert DataFrame to the dictionary format: {(God, Engine): Elo}
                    elo_ratings_db = elo_df.set_index(['God', 'Engine'])['Elo'].to_dict()
                    # Convert Elo scores back to BT scores for the model
                    initial_bt_ratings = convert_elo_to_bt(elo_ratings_db)
                    print(f"Loaded {len(initial_bt_ratings)} ratings from DB for warm start.")
                else:
                    print("TB_ELO is empty. Starting with default ratings.")
            else:
                print("TB_ELO table not found. Starting with default ratings.")
        except Exception as e:
            print(f"Could not load from DB for warm start: {e}. Starting with default ratings.")
        finally:
            conn.close()

    # 3. Fit the Model
    bt_ratings = fit_bradley_terry(items, wins_ij, matches_ij, max_iter=20000, initial_ratings=initial_bt_ratings)

    # 4. Convert Bradley-Terry scores to Elo
    elo_ratings = convert_bt_to_elo(bt_ratings)

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

    # 6. Save to Database if requested
    if save_to_db:
        print("\nAttempting to save Elo ratings to the database...")
        conn = get_conn()
        try:
            cursor = conn.cursor()
            create_table_query = """
            CREATE TABLE IF NOT EXISTS TB_ELO (
                "Engine" TEXT, "God" TEXT, "Elo" INTEGER NOT NULL, PRIMARY KEY("Engine", "God")
            )
            """
            cursor.execute(create_table_query)
            df_to_save = ranking_df[['Engine', 'God', 'Elo']].copy()
            df_to_save['Elo'] = df_to_save['Elo'].fillna(0).astype(int)
            print("Clearing old data from TB_ELO...")
            cursor.execute("DELETE FROM TB_ELO;")
            print("Inserting new data into TB_ELO...")
            df_to_save.to_sql('TB_ELO', conn, if_exists='append', index=False)
            conn.commit()
            print(f"✅ Successfully saved {len(df_to_save)} records to TB_ELO.")
        except Exception as e:
            conn.rollback()
            print(f"❌ Database operation failed: {e}")
        finally:
            conn.close()

    return ranking_df


# -------------------------------
# Helper Functions for Rating Conversion
# -------------------------------
def convert_bt_to_elo(bt_ratings: Dict[tuple, float]) -> Dict[tuple, float]:
    """
    Converts a dictionary of Bradley-Terry scores to Elo ratings,
    scaling the results so that the lowest rating is 0.
    """
    # Filter for valid BT scores (must be > 0 for log)
    valid_bt_ratings = {item: score for item, score in bt_ratings.items() if score > 0}

    if valid_bt_ratings:
        # Find the minimum positive Bradley-Terry score
        min_bt_score = np.min(list(valid_bt_ratings.values()))

        # The Elo formula is: Elo = 400 * log10(BT_score) + K
        # We want the Elo for the min_bt_score to be 0.
        # So, 0 = 400 * log10(min_bt_score) + K
        # This means K = -400 * log10(min_bt_score)
        K = -400 * np.log10(min_bt_score) if min_bt_score > 0 else 0

        # Calculate Elo for all items, assigning 0 to those with invalid BT scores
        elo_ratings = {
            item: (400 * np.log10(score) + K) if score > 0 else 0.0
            for item, score in bt_ratings.items()
        }
    else:
        # If there are no valid ratings, all Elos are 0
        elo_ratings = {item: 0.0 for item in bt_ratings.keys()}

    return elo_ratings


# --- NEW: Function to convert Elo back to BT for warm-starting ---
def convert_elo_to_bt(elo_ratings: Dict[tuple, float]) -> Dict[tuple, float]:
    """
    Converts a dictionary of Elo ratings back to Bradley-Terry scores.
    The absolute values don't matter, only their ratios, so we can ignore the 'K' constant.
    The core relationship is BT_score ∝ 10^(Elo / 400).
    """
    return {item: 10 ** (elo / 400) for item, elo in elo_ratings.items()}


# -------------------------------
# Main Execution Block
# -------------------------------
if __name__ == "__main__":
    engines_to_analyze = [
        "Fitos_1.1_Ton", "Fitos_2.1_Scout", "Fitos_3.2_Life", "Fitos_4.6_Atium", "Fitos_5.1_Truthless",
        "Fitos_6.3_Trick", "Fitos_7.2_Time", "Fitos_8.1_Cursed", "Fitos_9.4_Moth", "Fitos_10.5_Astro",
        "Fitos_11.0_Hyperion", "Fitos_12.0_Never", "Fitos_13.1_Legacy", "Fitos_14.8_Echo",
        "Paladini_1.4_Trigger", "Paladini_2.9_Apex", "Paladini_3.0_Summit", "Paladini_4.1.1_Mystic",
        "Paladini_5.5.40_Velocity", "Paladini_6.5.2_Prince", "Paladini_7.1.1_Lunar", "Paladini_8.1.8_Firefly",
        "Davi_1.0_Phoenix"
    ]

    # --- Example: Calculate ratings with a warm start from the DB and save the new results ---
    print("--- Running analysis with WARM START and saving to DB ---")
    final_rankings = calculate_ratings(
        include_engines=engines_to_analyze,
        save_to_db=True,
        display=True,
        warm_start_from_db=True  # Set this flag to True
    )