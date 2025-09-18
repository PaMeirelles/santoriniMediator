import pandas as pd
import itertools
from typing import Tuple, Dict

from analysis.rating_models.power_ranking import calculate_ratings
from game.board import God
from repopulate import (
    load_official_positions,
    prepare_position_string,
    run_single_match,
    get_conn,
    reverse_pos
)

# --- Tunable Constants for Scoring ---
W_LOW_TOTAL_GAMES = 1.8  # Prioritizes players that have a lower total game count.
W_ELO_CLOSENESS = 1.0
W_OPPONENT_SPREAD = 1.0

# --- Scheduler Configuration ---
NUM_MATCHES_TO_SCHEDULE = 12
GAMES_PER_SCHEDULED_MATCHUP = 2
STARTING_TIME = 60
POSITIONS_FILE_PATH = "../data/official_starting_pos.txt"


def load_data_for_scheduler() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads all necessary data for the scheduler in one place.
    1. Gets up-to-date Elos for each player (Engine-God).
    2. Gets total games played for each player. (CHANGED)
    3. Gets opponent-god counts for the spread score.

    Returns:
        A tuple of three DataFrames:
        - player_elos_df: ['Engine', 'God', 'Elo']
        - player_total_games_df: ['Engine', 'God', 'Total_Games']
        - opponent_spread_df: ['Engine', 'God', 'Opponent_God', 'Match_Count']
    """
    print("--- Loading all data for scheduler ---")
    conn = get_conn()

    # 1. Get current Elo ratings
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT Engine FROM VW_ENGINE_AVG_ELO")
    all_engines = [row[0] for row in cursor.fetchall()]
    if not all_engines:
        conn.close()
        raise ValueError("No engines found in the database.")

    print("Calculating current Elo ratings...")
    player_elos_df = calculate_ratings(include_engines=all_engines, save_to_db=False)
    player_elos_df = player_elos_df[['Engine', 'God', 'Elo']].copy()
    player_elos_df['Elo'] = pd.to_numeric(player_elos_df['Elo'])
    print(f"Loaded Elo for {len(player_elos_df)} players.")

    # 2. Get total games played per player using the view (CHANGED)
    print("Loading total games played per player...")
    total_games_query = """
    SELECT
        Engine,
        God,
        SUM(Match_Count) as Total_Games
    FROM
        VW_GAMES_PER_OPPONENT
    GROUP BY
        Engine, God;
    """
    player_total_games_df = pd.read_sql_query(total_games_query, conn)
    print(f"Loaded total game counts for {len(player_total_games_df)} players.")

    # 3. Get opponent spread data from the view
    print("Loading opponent spread data...")
    opponent_spread_df = pd.read_sql_query("SELECT * FROM VW_GAMES_PER_OPPONENT", conn)
    print(f"Loaded {len(opponent_spread_df)} opponent spread records.")

    conn.close()
    return player_elos_df, player_total_games_df, opponent_spread_df


def score_matches(player_elos: pd.DataFrame, player_total_games: pd.DataFrame,
                  opponent_spread: pd.DataFrame) -> pd.DataFrame:
    """
    Generates all possible matches, scores them based on the provided data, and returns a ranked DataFrame.
    """
    print("\n--- Scoring all potential matchups ---")

    # --- Pre-computation: Set indexes for much faster lookups ---
    player_elos_indexed = player_elos.set_index(['Engine', 'God'])
    player_total_games_indexed = player_total_games.set_index(['Engine', 'God'])
    opponent_spread_indexed = opponent_spread.set_index(['Engine', 'God', 'Opponent_God'])

    players = [tuple(x) for x in player_elos[['Engine', 'God']].to_numpy()]
    potential_matchups = list(itertools.combinations(players, 2))
    scored_matches = []

    for p1, p2 in potential_matchups:
        p1_engine, p1_god = p1
        p2_engine, p2_god = p2

        if p1_god == p2_god:
            continue

        p1_elo = player_elos_indexed.loc[p1, 'Elo']
        p2_elo = player_elos_indexed.loc[p2, 'Elo']

        # Get total games played for each player
        try:
            p1_total_games = player_total_games_indexed.loc[p1, 'Total_Games']
        except KeyError:
            p1_total_games = 0
        try:
            p2_total_games = player_total_games_indexed.loc[p2, 'Total_Games']
        except KeyError:
            p2_total_games = 0

        avg_total_games = (p1_total_games + p2_total_games) / 2.0
        score_low_total_games = 10.0 / (1.0 + avg_total_games)

        # Get games played vs specific opponent gods
        try:
            p1_games_vs_p2_god = opponent_spread_indexed.loc[(p1_engine, p1_god, p2_god), 'Match_Count']
        except KeyError:
            p1_games_vs_p2_god = 0
        try:
            p2_games_vs_p1_god = opponent_spread_indexed.loc[(p2_engine, p2_god, p1_god), 'Match_Count']
        except KeyError:
            p2_games_vs_p1_god = 0

        # Calculate the proportion of games against the opponent's god
        p1_proportion = (p1_games_vs_p2_god / p1_total_games) if p1_total_games > 0 else 0
        p2_proportion = (p2_games_vs_p1_god / p2_total_games) if p2_total_games > 0 else 0

        # The score is higher for lower proportions. A score of 1.0 means 0% of games were against this god.
        p1_spread_score = 1.0 - p1_proportion
        p2_spread_score = 1.0 - p2_proportion
        score_spread = (p1_spread_score + p2_spread_score) / 2.0

        # Calculate Elo score
        elo_diff = abs(p1_elo - p2_elo)
        score_elo_close = 1.0 / (1.0 + elo_diff / 100.0)

        # Calculate final weighted score
        total_score = (
                W_LOW_TOTAL_GAMES * score_low_total_games +
                W_ELO_CLOSENESS * score_elo_close +
                W_OPPONENT_SPREAD * score_spread
        )

        scored_matches.append({
            'Player 1': f"{p1_engine} ({p1_god})",
            'Player 2': f"{p2_engine} ({p2_god})",
            'Total Score': total_score,
            'Low Games Score': score_low_total_games * W_LOW_TOTAL_GAMES,
            'Elo Close Score': score_elo_close * W_ELO_CLOSENESS,
            'Spread Score': score_spread * W_OPPONENT_SPREAD,
            'p1_tuple': p1, 'p2_tuple': p2
        })

    return pd.DataFrame(scored_matches).sort_values(by='Total Score', ascending=False).reset_index(drop=True)

def main():
    """Main function to run the dynamic scheduler."""
    try:
        player_elos, player_total_games, opponent_spread = load_data_for_scheduler()
    except (ValueError, FileNotFoundError) as e:
        print(f"Error during data loading: {e}")
        return

    schedule_df = score_matches(player_elos, player_total_games, opponent_spread)

    if schedule_df.empty:
        print("No valid matchups could be scored.")
        return

    # 3. Display the schedule
    print(f"\n--- Top {NUM_MATCHES_TO_SCHEDULE} Scheduled Matches ---")
    display_cols = ['Player 1', 'Player 2', 'Total Score', 'Low Games Score', 'Elo Close Score', 'Spread Score']

    display_df = schedule_df[display_cols].head(NUM_MATCHES_TO_SCHEDULE).copy()
    for col in display_cols[2:]:
        display_df[col] = display_df[col].map('{:.4f}'.format)

    print(display_df.to_string())

    # 4. Play the scheduled matches (This function remains unchanged)
    play_scheduled_matches(schedule_df)

    print("\nScheduler run finished. Run the script again to schedule the next batch.")


# The play_scheduled_matches function from the previous response remains the same
def play_scheduled_matches(schedule: pd.DataFrame):
    """
    Takes the top matches from the schedule and plays them.
    """
    print("\n--- Preparing to play scheduled matches ---")

    official_positions = load_official_positions(POSITIONS_FILE_PATH)
    if not official_positions:
        print("Halting execution due to missing positions file.")
        return

    conn = get_conn()
    cursor = conn.cursor()

    for i, match in schedule.head(NUM_MATCHES_TO_SCHEDULE).iterrows():
        (p1_engine, p1_god_name), (p2_engine, p2_god_name) = match['p1_tuple'], match['p2_tuple']

        p1_god = God[p1_god_name]
        p2_god = God[p2_god_name]

        print(f"\n--- Playing Matchup #{i + 1}: {match['Player 1']} vs {match['Player 2']} ---")

        for j in range(GAMES_PER_SCHEDULED_MATCHUP // 2):
            template_pos = official_positions[j % len(official_positions)]

            pos1 = prepare_position_string(template_pos, p1_god, p2_god)
            run_single_match(cursor, p1_engine, p2_engine, p1_god, p2_god, STARTING_TIME, pos1)
            conn.commit()

            pos2 = reverse_pos(pos1)
            run_single_match(cursor, p2_engine, p1_engine, p2_god, p1_god, STARTING_TIME, pos2)
            conn.commit()

    print("\n--- Scheduled match session complete. ---")
    conn.close()


if __name__ == "__main__":
    main()