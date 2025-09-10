import pandas as pd
import numpy as np
from scipy.optimize import minimize
from collections import defaultdict
from analysis.visualization.visualization import get_conn # Assuming this connects to your DB

# -------------------------------
# Configuration
# -------------------------------
INCLUDE_ENGINES = [
    "Fitos_4.6_Atium", "Fitos_5.1_Truthless", "Fitos_6.3_Trick",
    "Fitos_7.2_Time", "Fitos_8.1_Cursed", "Fitos_9.4_Moth",
    "Fitos_10.5_Astro", "Fitos_11.0_Hyperion", "Fitos_12.0_Never", "Fitos_13.1_Legacy",
    "Paladini_1.4_Trigger", "Paladini_2.9_Apex", "Paladini_3.0_Summit",
    "Paladini_4.1.1_Mystic"
]
ELO_SCALE = 400.0  # Standard Elo scale factor

# -------------------------------
# Data Loading and Preparation
# -------------------------------
def load_and_prepare_data(engine_list: list) -> tuple:
    """Loads match data and prepares it for the optimizer."""
    engine_list_sql = ", ".join(f"'{engine}'" for engine in engine_list)
    conn = get_conn()
    query = f"""
        SELECT
            Engine_G, God_G, Engine_B, God_B, Result
        FROM TB_MATCHES
        WHERE Engine_G IN ({engine_list_sql}) AND Engine_B IN ({engine_list_sql})
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    player_stats = defaultdict(lambda: {'wins': 0, 'matches': 0})
    player_opponents = defaultdict(lambda: defaultdict(int))

    for _, row in df.iterrows():
        p1 = (row['God_G'], row['Engine_G'])
        p2 = (row['God_B'], row['Engine_B'])

        # Update match counts for both players
        player_stats[p1]['matches'] += 1
        player_stats[p2]['matches'] += 1
        player_opponents[p1][p2] += 1
        player_opponents[p2][p1] += 1

        # Update win count for the winner
        if row['Result'] == 1:
            player_stats[p1]['wins'] += 1
        elif row['Result'] == -1:
            player_stats[p2]['wins'] += 1
        # Draws (Result=0) add matches but no wins

    players = sorted(player_stats.keys())
    return players, player_stats, player_opponents

# -------------------------------
# The Objective (Loss) Function
# -------------------------------
def objective_function(ratings_array: np.ndarray, players: list, stats: dict, opponents: dict) -> float:
    """
    This is the core loss function we want to minimize.
    It calculates the total squared error between actual and expected win rates.
    """
    ratings_dict = {player: rating for player, rating in zip(players, ratings_array)}
    total_squared_error = 0.0

    for player in players:
        # 1. Calculate Actual Performance (Win Rate)
        total_matches = stats[player]['matches']
        if total_matches == 0:
            continue
        actual_win_rate = stats[player]['wins'] / total_matches

        # 2. Calculate Expected Performance (based on opponents and trial ratings)
        total_expected_score = 0.0
        player_rating = ratings_dict[player]

        for opponent, num_games in opponents[player].items():
            opponent_rating = ratings_dict.get(opponent, 1500.0) # Default for safety
            expected_score = 1.0 / (1.0 + 10**((opponent_rating - player_rating) / ELO_SCALE))
            total_expected_score += expected_score * num_games

        expected_win_rate = total_expected_score / total_matches

        # 3. Add the squared difference to the total loss
        total_squared_error += (actual_win_rate - expected_win_rate)**2

    return total_squared_error

# -------------------------------
# Main Execution
# -------------------------------
def main():
    """Main function to run the optimization and display results."""
    print("Loading and preparing data...")
    players, player_stats, player_opponents = load_and_prepare_data(INCLUDE_ENGINES)
    num_players = len(players)
    print(f"Found {num_players} unique God-Engine pairs.")

    print("\nStarting optimization to find the best-fit ratings...")
    # Initial guess for all ratings is 1500
    initial_ratings = np.full(num_players, 1500.0)

    # The arguments to pass to our objective function
    args = (players, player_stats, player_opponents)

    # Run the optimizer
    result = minimize(
        fun=objective_function,
        x0=initial_ratings,
        args=args,
        method='BFGS',  # A popular and effective optimization algorithm
        options={'disp': True, 'maxiter': 5000}
    )

    if not result.success:
        print("\nWarning: Optimization may not have converged.")
        print("Message:", result.message)

    # Extract final ratings and display them
    final_ratings = result.x
    results_data = []
    for i, player in enumerate(players):
        god, engine = player
        wins = player_stats[player]['wins']
        matches = player_stats[player]['matches']
        win_rate = (wins / matches * 100) if matches > 0 else 0
        results_data.append({
            "God": god,
            "Engine": engine,
            "Rating": final_ratings[i],
            "Win Rate (%)": win_rate,
            "Matches": matches,
            "Wins": wins
        })

    results_df = pd.DataFrame(results_data)
    results_df.sort_values(by="Rating", ascending=False, inplace=True)
    results_df.reset_index(drop=True, inplace=True)

    print("\n--- Final Ratings from Optimization ---")
    print(results_df.to_string(index=False))

    avg_opposition_data = []

    ratings_dict = {player: rating for player, rating in zip(players, final_ratings)}

    for player in players:
        opponents_dict = player_opponents[player]
        total_matches = sum(opponents_dict.values())
        if total_matches == 0:
            avg_opponent_rating = np.nan
        else:
            # Weighted average rating of opponents
            weighted_sum = sum(ratings_dict[opp] * count for opp, count in opponents_dict.items())
            avg_opponent_rating = weighted_sum / total_matches

        god, engine = player
        avg_opposition_data.append({
            "God": god,
            "Engine": engine,
            "Avg Opposition Rating": avg_opponent_rating,
            "Matches": total_matches
        })

    avg_opposition_df = pd.DataFrame(avg_opposition_data)
    avg_opposition_df.sort_values(by="Avg Opposition Rating", ascending=False, inplace=True)
    avg_opposition_df.reset_index(drop=True, inplace=True)

    print("\n--- Average Opposition Ratings ---")
    print(avg_opposition_df.to_string(index=False))

if __name__ == "__main__":
    main()
