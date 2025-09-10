import pandas as pd
import numpy as np
from collections import defaultdict
from analysis.database import get_conn

# --- Configuration ---
ALLOWED_ENGINES = {
    "Fitos_1.1_Ton",
    "Fitos_2.1_Scout",
    "Fitos_3.2_Life",
    "Fitos_4.6_Atium",
    "Fitos_5.1_Truthless",
    "Fitos_6.3_Trick",
    "Fitos_7.2_Time",
    "Fitos_8.1_Cursed",
    "Fitos_9.4_Moth",
    "Fitos_10.5_Astro",
    "Fitos_11.0_Hyperion",
    "Fitos_12.0_Never",
    "Fitos_13.1_Legacy",
    "Fitos_14.8_Echo",
    "Paladini_1.4_Trigger",
    "Paladini_2.9_Apex",
    "Paladini_3.0_Summit",
    "Paladini_4.1.1_Mystic",
    "Paladini_5.5.11_Velocity",
}

ANCHOR_ENGINE = 'Fitos_1.1_Ton'
ANCHOR_ELO = 0.0
ITERATIONS = 100
ELO_SCALE = 400.0  # Standard Elo scale factor


def get_expected_score(r1, r2, scale):
    """Calculates the expected win probability for player 1."""
    # Clamp the difference to a reasonable range to prevent overflow
    clamped_delta = max(-800.0, min(r2 - r1, 800.0))
    return 1.0 / (1.0 + 10 ** (clamped_delta / scale))


def calculate_ratings():
    """
    Calculates Elo ratings for all (engine, god) pairs using Maximum Likelihood Estimation,
    considering only the engines specified in ALLOWED_ENGINES.
    """
    print("Loading match data from database for allowed engines...")
    conn = get_conn()

    placeholders = ', '.join(['?'] * len(ALLOWED_ENGINES))

    query = f"""
        SELECT * FROM TB_MATCHES 
        WHERE Engine_G IN ({placeholders}) AND Engine_B IN ({placeholders})
    """

    params = list(ALLOWED_ENGINES) * 2

    df = pd.read_sql_query(query, conn, params=params)

    conn.close()

    players = set()
    games = []

    print(f"Processing {len(df)} games and identifying players...")
    for _, row in df.iterrows():
        player_g = (row['Engine_G'], row['God_G'])
        player_b = (row['Engine_B'], row['God_B'])
        players.add(player_g)
        players.add(player_b)

        # --- MODIFICATION START ---
        # Convert database result (1 for Gold win, -1 for Blue win) to Elo score (1.0, 0.0)
        db_result = row['Result']
        if db_result >= 1:
            game_score = 1.0  # Win for Player 1 (Gold)
        elif db_result <= -1:
            game_score = 0.0  # Loss for Player 1 (Gold)
        else:
            game_score = 0.5  # Assume any other result (like 0) is a draw
        # --- MODIFICATION END ---

        games.append({'p1': player_g, 'p2': player_b, 'result': game_score})

    # Initialize ratings
    ratings = {player: ANCHOR_ELO for player in players}

    print(f"Starting iterative rating calculation for {len(players)} players over {len(games)} games...")
    for i in range(ITERATIONS):
        numerators = defaultdict(float)
        denominators = defaultdict(float)

        for game in games:
            p1, p2 = game['p1'], game['p2']
            r1, r2 = ratings[p1], ratings[p2]
            expected = get_expected_score(r1, r2, ELO_SCALE)

            numerators[p1] += game['result'] - expected
            numerators[p2] += (1 - game['result']) - (1 - expected)

            variance = expected * (1 - expected)
            denominators[p1] += variance
            denominators[p2] += variance

        for player in players:
            if denominators[player] > 0:
                ratings[player] += numerators[player] / denominators[player]

        anchor_players = [p for p in players if p[0] == ANCHOR_ENGINE]
        if anchor_players:
            avg_anchor_elo = sum(ratings[p] for p in anchor_players) / len(anchor_players)
            elo_shift = ANCHOR_ELO - avg_anchor_elo
            ratings = {p: r + elo_shift for p, r in ratings.items()}

        if (i + 1) % 10 == 0:
            print(f"Iteration {i + 1}/{ITERATIONS} complete.")

    print("\n--- Final Elo Ratings ---")
    sorted_ratings = sorted(ratings.items(), key=lambda item: item[1], reverse=True)
    for player, rating in sorted_ratings:
        print(f"{rating:8.2f} ELO | {player[0]} ({player[1]})")

    return ratings


if __name__ == "__main__":
    calculate_ratings()