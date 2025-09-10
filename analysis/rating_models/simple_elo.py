import pandas as pd
import numpy as np
from collections import defaultdict
import random
from analysis.database import get_conn  # Assuming this connects to your DB

# --- Configuration ---
ALLOWED_ENGINES = {
    # "Fitos_1.1_Ton",
    # "Fitos_2.1_Scout",
    # "Fitos_3.2_Life",
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
    # "Paladini_5.5.11_Velocity",
}

INITIAL_ELO = 1500.0
K_FACTOR = 32.0  # Determines the maximum rating change from a single game
ELO_SCALE = 400.0  # Standard Elo scale factor
N_BOOTSTRAP_RUNS = 1000  # Number of times to shuffle, run, and average


def get_expected_score(r1, r2):
    """Calculates the expected win probability for player 1."""
    return 1.0 / (1.0 + 10 ** ((r2 - r1) / ELO_SCALE))


def calculate_sequential_elo(games, players):
    """
    Calculates Elo ratings for a single pass using a standard sequential update model.
    """
    ratings = {player: INITIAL_ELO for player in players}

    # Process each game sequentially and update ratings immediately
    for game in games:
        p1, p2 = game['p1'], game['p2']
        s1 = game['result']

        r1 = ratings[p1]
        r2 = ratings[p2]

        e1 = get_expected_score(r1, r2)
        rating_change = K_FACTOR * (s1 - e1)

        ratings[p1] += rating_change
        ratings[p2] -= rating_change

    return ratings


def run_bootstrapped_calculation():
    """
    Main function to load data, run the bootstrapped sequential Elo model, and print results.
    """
    print("Loading match data from database...")
    conn = get_conn()
    placeholders = ', '.join(['?'] * len(ALLOWED_ENGINES))
    query = f"SELECT * FROM TB_MATCHES WHERE Engine_G IN ({placeholders}) AND Engine_B IN ({placeholders})"
    params = list(ALLOWED_ENGINES) * 2
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    players = set()
    games = []
    print(f"Processing {len(df)} games and identifying unique players...")
    for _, row in df.iterrows():
        player_g = (row['Engine_G'], row['God_G'])
        player_b = (row['Engine_B'], row['God_B'])
        players.add(player_g)
        players.add(player_b)

        db_result = row['Result']
        if db_result >= 1:
            game_score = 1.0
        elif db_result <= -1:
            game_score = 0.0
        else:
            game_score = 0.5
        games.append({'p1': player_g, 'p2': player_b, 'result': game_score})

    print(f"Found {len(players)} unique players.")
    print(f"Starting {N_BOOTSTRAP_RUNS} bootstrap runs of the sequential Elo model...")

    all_ratings_history = defaultdict(list)

    for i in range(N_BOOTSTRAP_RUNS):
        print(f"  - Running bootstrap iteration {i + 1}/{N_BOOTSTRAP_RUNS}...")
        random.shuffle(games)

        # Run the sequential Elo calculation for this shuffled order
        current_run_ratings = calculate_sequential_elo(games, players)

        # Store the results for averaging later
        for player, rating in current_run_ratings.items():
            all_ratings_history[player].append(rating)

    print("\nCalculating final averaged ratings and standard deviations...")
    final_averaged_ratings = []
    for player, rating_history in all_ratings_history.items():
        avg_rating = np.mean(rating_history)
        std_dev = np.std(rating_history)
        final_averaged_ratings.append({
            'player': player,
            'avg_rating': avg_rating,
            'std_dev': std_dev
        })

    # Sort by the final average rating
    sorted_final_ratings = sorted(final_averaged_ratings, key=lambda x: x['avg_rating'], reverse=True)

    print("\n--- Final Averaged Sequential Elo Ratings ---")
    print(f"{'Avg Rating':>12} {'Std Dev':>10}   {'Player'}")
    print("-" * 80)
    for entry in sorted_final_ratings:
        player_str = f"{entry['player'][0]} ({entry['player'][1]})"
        print(f"{entry['avg_rating']:>12.2f} {entry['std_dev']:>10.2f}   {player_str}")

    return sorted_final_ratings


if __name__ == "__main__":
    run_bootstrapped_calculation()