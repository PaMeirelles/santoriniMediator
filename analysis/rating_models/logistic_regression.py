import pandas as pd
import numpy as np
from sqlalchemy import text
from sklearn.linear_model import LogisticRegression
from scipy.sparse import csr_matrix

from database.postgres.postgres_interface import get_engine


def load_matches(engine) -> pd.DataFrame:
    """
    Loads all matches and their participants from the PostgreSQL database.
    According to the migration interface:
    - side = TRUE is Gray, side = FALSE is Blue
    - winner_side = TRUE means Gray won, FALSE means Blue won
    """
    query = text("""
        SELECT 
            eng_gray.engine_name AS gray_engine, 
            god_gray.god_name AS gray_god,
            eng_blue.engine_name AS blue_engine, 
            god_blue.god_name AS blue_god,
            m.winner_side
        FROM tb_matches m
        JOIN tb_match_participants part_gray 
            ON m.match_id = part_gray.match_id AND part_gray.side = TRUE
        JOIN tb_engines eng_gray 
            ON part_gray.engine_id = eng_gray.engine_id
        JOIN tb_gods god_gray 
            ON part_gray.god_id = god_gray.god_id
        JOIN tb_match_participants part_blue 
            ON m.match_id = part_blue.match_id AND part_blue.side = FALSE
        JOIN tb_engines eng_blue 
            ON part_blue.engine_id = eng_blue.engine_id
        JOIN tb_gods god_blue 
            ON part_blue.god_id = god_blue.god_id
    """)

    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df


# ---------------------------------------------------------
# Rating Calculation (Bradley-Terry via Logistic Regression)
# ---------------------------------------------------------
def calculate_ratings(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        print("No matches found in the database.")
        return pd.DataFrame()

    # Create tuples to represent the unique God-Engine pairs
    df['gray_item'] = list(zip(df['gray_god'], df['gray_engine']))
    df['blue_item'] = list(zip(df['blue_god'], df['blue_engine']))

    # Determine winner and loser items based on winner_side (True = Gray, False = Blue)
    df['winner'] = np.where(df['winner_side'] == True, df['gray_item'], df['blue_item'])
    df['loser'] = np.where(df['winner_side'] == True, df['blue_item'], df['gray_item'])

    # Extract unique items and map them to indices
    items = sorted(list(set(df['winner']).union(set(df['loser']))))
    item_to_idx = {item: i for i, item in enumerate(items)}

    # Prepare sparse matrix for Logistic Regression
    rows = []
    cols = []
    data = []

    for idx, row in enumerate(df.itertuples()):
        rows.extend([idx, idx])
        # Winner gets a +1 feature, Loser gets a -1 feature
        cols.extend([item_to_idx[row.winner], item_to_idx[row.loser]])
        data.extend([1, -1])

    X = csr_matrix((data, (rows, cols)), shape=(len(df), len(items)))
    y = np.ones(len(df))  # Target is always 1 (because we set X relative to the winner)

    # Fit the model
    # Using L2 penalty (Ridge) acts as a Bayesian prior, preventing infinite ratings
    # for engines that have a 100% win rate or 0% win rate.
    model = LogisticRegression(penalty='l2', C=1.0, fit_intercept=False, solver='lbfgs', max_iter=1000)
    model.fit(X, y)

    # Extract coefficients (log-odds) and convert to Bradley-Terry probabilities
    betas = model.coef_[0]
    bt_scores = np.exp(betas)

    # Scale BT scores to Elo (anchoring the lowest rating to 0)
    min_bt = np.min(bt_scores[bt_scores > 0])
    K = -400 * np.log10(min_bt) if min_bt > 0 else 0
    elos = {items[i]: 400 * np.log10(score) + K for i, score in enumerate(bt_scores)}

    # Compile the final statistics
    wins_counts = df['winner'].value_counts()
    matches_counts = pd.concat([df['winner'], df['loser']]).value_counts()

    results = []
    for item in items:
        god, engine = item
        wins = wins_counts.get(item, 0)
        matches = matches_counts.get(item, 0)
        win_rate = (wins / matches * 100) if matches > 0 else 0.0

        results.append({
            "God": god,
            "Engine": engine,
            "Matches": matches,
            "Wins": wins,
            "Win Rate (%)": win_rate,
            "Elo": elos[item]
        })

    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(by="Elo", ascending=False).reset_index(drop=True)

    return res_df


# ---------------------------------------------------------
# Main Execution
# ---------------------------------------------------------
if __name__ == "__main__":
    db_engine = get_engine()
    print("Loading matches from PostgreSQL...")

    matches_df = load_matches(db_engine)
    print(f"Loaded {len(matches_df)} matches.\n")

    print("Calculating order-invariant ratings (L-BFGS)...")
    ranking_df = calculate_ratings(matches_df)

    if not ranking_df.empty:
        # Formatting for console display
        display_df = ranking_df.copy()
        display_df['Win Rate (%)'] = display_df['Win Rate (%)'].map('{:.2f}'.format)
        display_df['Elo'] = display_df['Elo'].map('{:.0f}'.format)

        print("\n" + "=" * 70)
        print(f"{'Ranking of God-Engine Pairs':^70}")
        print("=" * 70)

        # Configure Pandas to print all rows cleanly
        pd.set_option('display.max_rows', None)
        pd.set_option('display.width', 1000)
        print(display_df.to_string())
        print("=" * 70)