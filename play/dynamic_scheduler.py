import pandas as pd
import itertools
import random
import concurrent.futures
from tqdm import tqdm
from typing import Tuple, Dict, Optional, Set, List, Any
import re  # NEW: Import for regular expressions

# Adjust import paths based on your project structure
from analysis.rating_models.power_ranking import calculate_ratings
from game.board import God
from repopulate import (
    load_official_positions,
    prepare_position_string,
    get_conn,
    reverse_pos
)
# --- NEW IMPORTS for parallel execution ---
from client.controller import Controller
from game.constants import ENGINES
from analysis.database import store_match

# --- Tunable Constants for Scoring ---
W_LOW_TOTAL_GAMES = 1.0
W_ELO_CLOSENESS = 1.0
W_OPPONENT_SPREAD = 1.0
W_ELO_ANOMALY = 1.5  # NEW: Prioritizes matches to resolve Elo inconsistencies

# --- Scheduler Configuration ---
NUM_MATCHES_TO_SCHEDULE = 120
GAMES_PER_SCHEDULED_MATCHUP = 2  # Implicitly handled by playing symmetric pairs
STARTING_TIME = 60
POSITIONS_FILE_PATH = "../data/official_starting_pos.txt"
MAX_WORKERS = 12  # Number of games to run in parallel


class Colors:
    RED = '\033[91m'
    LIGHT_GREEN = '\033[92m'
    YELLOW = '\033[93m'
    LIGHT_BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GREY = '\033[90m'
    DARK_GREEN = '\033[32m'
    ORANGE = '\033[38;5;208m'
    BROWN = '\033[38;5;94m'
    ENDC = '\033[0m'


GOD_COLORS = {
    # Thematic Color Assignments
    God.APOLLO: Colors.YELLOW,
    God.ARTEMIS: Colors.CYAN,
    God.ATHENA: Colors.WHITE,
    God.ATLAS: Colors.GREY,
    God.DEMETER: Colors.DARK_GREEN,
    God.HEPHAESTUS: Colors.ORANGE,
    God.HERMES: Colors.LIGHT_BLUE,
    God.MINOTAUR: Colors.BROWN,
    God.PAN: Colors.LIGHT_GREEN,
    God.PROMETHEUS: Colors.RED
}


def print_elo_ranking_table(current_elos: pd.DataFrame, previous_elos: Optional[pd.DataFrame]):
    """
    Prints a formatted table of players, their rank, Elo, rank change, and Elo change.
    """
    TABLE_WIDTH = 95
    print("\n" + "=" * TABLE_WIDTH)
    print(" " * 35 + "CURRENT PLAYER RANKINGS")
    print("=" * TABLE_WIDTH)

    ranked_df = current_elos.sort_values(by='Elo', ascending=False).copy()
    ranked_df['Rank'] = range(1, len(ranked_df) + 1)

    if previous_elos is not None:
        previous_ranked_df = previous_elos.sort_values(by='Elo', ascending=False).copy()
        previous_ranked_df['Rank_prev'] = range(1, len(previous_ranked_df) + 1)
        ranked_df = pd.merge(
            ranked_df,
            previous_ranked_df[['Engine', 'God', 'Elo', 'Rank_prev']],
            on=['Engine', 'God'],
            how='left',
            suffixes=('', '_prev')
        )

    PLAYER_COL_WIDTH = 48
    print(f"{'Rank':<5} {'Player':<{PLAYER_COL_WIDTH}} {'Elo':<12} {'Rank Δ':<12} {'Elo Δ'}")
    print(f"{'-' * 4:<5} {'-' * (PLAYER_COL_WIDTH - 1):<{PLAYER_COL_WIDTH}} {'-' * 11:<12} {'-' * 11:<12} {'-' * 5}")

    for _, row in ranked_df.iterrows():
        god_color = GOD_COLORS.get(God[row['God']], Colors.WHITE)
        player_str_for_print = f"{row['Engine']} ({god_color}{row['God']}{Colors.ENDC})"
        visible_length = len(row['Engine']) + len(row['God']) + 3
        padding_needed = max(0, PLAYER_COL_WIDTH - visible_length)
        padding = ' ' * padding_needed

        rank_change_str = f"{Colors.GREY}-{Colors.ENDC}"
        elo_change_str = f"{Colors.GREY}-{Colors.ENDC}"

        if previous_elos is not None and not pd.isna(row.get('Elo_prev')):
            elo_diff = row['Elo'] - row['Elo_prev']
            rank_diff = row['Rank_prev'] - row['Rank']
            if rank_diff > 0:
                rank_change_str = f"{Colors.LIGHT_GREEN}▲ {int(rank_diff)}{Colors.ENDC}"
            elif rank_diff < 0:
                rank_change_str = f"{Colors.RED}▼ {abs(int(rank_diff))}{Colors.ENDC}"
            if elo_diff > 0:
                elo_change_str = f"{Colors.LIGHT_GREEN}▲ {elo_diff:+.2f}{Colors.ENDC}"
            elif elo_diff < 0:
                elo_change_str = f"{Colors.RED}▼ {elo_diff:+.2f}{Colors.ENDC}"
            else:
                elo_change_str = f"{Colors.GREY}{elo_diff:+.2f}{Colors.ENDC}"
        elif previous_elos is not None:
            rank_change_str = f"{Colors.YELLOW}New{Colors.ENDC}"
            elo_change_str = f"{Colors.YELLOW}New{Colors.ENDC}"

        print(
            f"{row['Rank']:<5} {player_str_for_print}{padding} {row['Elo']:<12.2f} {rank_change_str:<20} {elo_change_str}")

    print("=" * TABLE_WIDTH + "\n")


def load_data_for_scheduler() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads all Elo, game count, and opponent spread data from the database."""
    print("--- Loading all data for scheduler ---")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT Engine FROM VW_ENGINE_AVG_ELO")
    all_engines = [row[0] for row in cursor.fetchall()]
    if not all_engines:
        conn.close()
        raise ValueError("No engines found in the database.")

    print("Calculating current Elo ratings...")
    player_elos_df = calculate_ratings(include_engines=all_engines, save_to_db=True, warm_start_from_db=True)
    player_elos_df = player_elos_df[['Engine', 'God', 'Elo']].copy()
    player_elos_df['Elo'] = pd.to_numeric(player_elos_df['Elo'])
    print(f"Loaded Elo for {len(player_elos_df)} players.")

    print("Loading total games played per player...")
    total_games_query = "SELECT Engine, God, SUM(Match_Count) as Total_Games FROM VW_GAMES_PER_OPPONENT GROUP BY Engine, God;"
    player_total_games_df = pd.read_sql_query(total_games_query, conn)
    print(f"Loaded total game counts for {len(player_total_games_df)} players.")

    print("Loading opponent spread data...")
    opponent_spread_df = pd.read_sql_query("SELECT * FROM VW_GAMES_PER_OPPONENT", conn)
    print(f"Loaded {len(opponent_spread_df)} opponent spread records.")

    conn.close()
    return player_elos_df, player_total_games_df, opponent_spread_df


def get_engine_strength(engine_name: str) -> int:
    """
    Parses an engine name to determine its relative strength based on a defined hierarchy.
    Higher return value means a stronger engine.
    """
    engine_name_lower = engine_name.lower()

    # Extracts the first number found, which corresponds to the major version.
    version_match = re.search(r'(\d+)', engine_name_lower)
    major_version = 0
    if version_match:
        major_version = int(version_match.group(1))

    if 'paladini' in engine_name_lower:
        base_strength = 100
        return base_strength + major_version

    if 'fitos' in engine_name_lower:
        # Base strength for Fitos is lower than Paladini
        return 10 + major_version

    return 0  # Default for any other engines

def find_elo_anomalies(player_elos: pd.DataFrame) -> Set[Tuple[str, str]]:
    """
    Identifies engine-god pairs where a stronger engine has a lower Elo than a
    weaker engine for the same god. Returns a set of (Engine, God) tuples involved.
    """
    anomaly_players = set()
    player_elos['strength'] = player_elos['Engine'].apply(get_engine_strength)

    for god, group in player_elos.groupby('God'):
        if len(group) < 2:
            continue

        for (idx1, p1), (idx2, p2) in itertools.combinations(group.iterrows(), 2):
            p1_strength, p2_strength = p1['strength'], p2['strength']
            p1_elo, p2_elo = p1['Elo'], p2['Elo']

            # Anomaly: stronger engine has lower Elo
            if (p1_strength > p2_strength and p1_elo < p2_elo) or \
                    (p2_strength > p1_strength and p2_elo < p1_elo):
                anomaly_players.add((p1['Engine'], god))
                anomaly_players.add((p2['Engine'], god))
    return anomaly_players


def score_matches(player_elos: pd.DataFrame, player_total_games: pd.DataFrame,
                  opponent_spread: pd.DataFrame) -> pd.DataFrame:
    """Scores all potential matchups based on a weighted combination of factors."""
    print("\n--- Scoring all potential matchups ---")

    anomaly_players = find_elo_anomalies(player_elos.copy())
    if anomaly_players:
        print(f"Found {len(anomaly_players)} players involved in Elo anomalies. They will be prioritized.")

    player_elos_indexed = player_elos.set_index(['Engine', 'God'])
    player_total_games_indexed = player_total_games.set_index(['Engine', 'God'])
    opponent_spread_indexed = opponent_spread.set_index(['Engine', 'God', 'Opponent_God'])
    players = [tuple(x) for x in player_elos[['Engine', 'God']].to_numpy()]
    potential_matchups = list(itertools.combinations(players, 2))
    scored_matches = []

    for p1, p2 in potential_matchups:
        p1_engine, p1_god = p1
        p2_engine, p2_god = p2
        if p1_god == p2_god: continue

        p1_elo = player_elos_indexed.loc[p1, 'Elo']
        p2_elo = player_elos_indexed.loc[p2, 'Elo']

        try:
            p1_total_games = player_total_games_indexed.loc[p1, 'Total_Games']
        except KeyError:
            p1_total_games = 0

        try:
            p2_total_games = player_total_games_indexed.loc[p2, 'Total_Games']
        except KeyError:
            p2_total_games = 0

        avg_total_games = (p1_total_games + p2_total_games) / 2.0
        score_low_total_games = 30 / (1.0 + avg_total_games)

        try:
            p1_games_vs_p2_god = opponent_spread_indexed.loc[(p1_engine, p1_god, p2_god), 'Match_Count']
        except KeyError:
            p1_games_vs_p2_god = 0

        try:
            p2_games_vs_p1_god = opponent_spread_indexed.loc[(p2_engine, p2_god, p1_god), 'Match_Count']
        except KeyError:
            p2_games_vs_p1_god = 0

        p1_proportion = (p1_games_vs_p2_god / p1_total_games) if p1_total_games > 0 else 0
        p2_proportion = (p2_games_vs_p1_god / p2_total_games) if p2_total_games > 0 else 0
        p1_spread_score = 1.0 - p1_proportion
        p2_spread_score = 1.0 - p2_proportion
        score_spread = (p1_spread_score + p2_spread_score) / 2.0

        elo_diff = abs(p1_elo - p2_elo)
        score_elo_close = 1.0 / (1.0 + elo_diff / 100.0)

        # NEW: Calculate Elo Anomaly Score
        score_elo_anomaly = 1.0 if p1 in anomaly_players or p2 in anomaly_players else 0.0

        total_score = (
                W_LOW_TOTAL_GAMES * score_low_total_games +
                W_ELO_CLOSENESS * score_elo_close +
                W_OPPONENT_SPREAD * score_spread +
                W_ELO_ANOMALY * score_elo_anomaly  # NEW: Added anomaly score
        )
        scored_matches.append({
            'Player 1': f"{p1_engine} ({p1_god})", 'Player 2': f"{p2_engine} ({p2_god})",
            'Total Score': total_score, 'Low Games Score': score_low_total_games * W_LOW_TOTAL_GAMES,
            'Elo Close Score': score_elo_close * W_ELO_CLOSENESS, 'Spread Score': score_spread * W_OPPONENT_SPREAD,
            'Elo Anomaly Score': score_elo_anomaly * W_ELO_ANOMALY,  # NEW: Store anomaly score
            'p1_tuple': p1, 'p2_tuple': p2
        })
    return pd.DataFrame(scored_matches).sort_values(by='Total Score', ascending=False).reset_index(drop=True)


def get_played_matches(cursor) -> Set[Tuple[str, str, str, int]]:
    """
    Fetches a set of all previously played match configurations for fast lookups.
    Returns a set of (Starting_pos, Engine_G, Engine_B, Time_G) tuples.
    """
    print("Fetching history of played matches from the database...")
    cursor.execute("SELECT Starting_pos, Engine_G, Engine_B, Time_G FROM TB_MATCHES WHERE Time_G = Time_B")
    return set(cursor.fetchall())


def play_game_worker(game_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker function to run a single game in a separate thread.
    This function does NOT interact with the database.
    """
    engine_g, engine_b = game_params['engine_g'], game_params['engine_b']
    god_g, god_b = game_params['god_g'], game_params['god_b']
    pos, starting_time = game_params['pos'], game_params['starting_time']

    ctrl = Controller(pos, starting_time, starting_time, ENGINES[engine_g], ENGINES[engine_b], headless=True)
    result, moves = ctrl.run_game()

    return {
        'god_a': god_g, 'god_b': god_b, 'engine_name_g': engine_g,
        'engine_name_b': engine_b, 'result': result, 'starting_time': starting_time,
        'moves': moves, 'pos': pos
    }


def play_scheduled_matches(schedule: pd.DataFrame):
    """
    Takes top matches, prepares unplayed games, executes them in parallel, and saves results.
    """
    print("\n--- Preparing to play scheduled matches ---")

    # Phase 1: Load static data and database history
    official_positions = load_official_positions(POSITIONS_FILE_PATH)
    if not official_positions:
        print("Halting execution due to missing positions file.")
        return

    conn = get_conn()
    cursor = conn.cursor()
    played_matches = get_played_matches(cursor)
    conn.close()
    print(f"Found {len(played_matches)} previously played matches for fast checking.")

    # Phase 2: Build the list of games to play
    games_to_play: List[Dict] = []
    for i, match in schedule.head(NUM_MATCHES_TO_SCHEDULE).iterrows():
        (p1_engine, p1_god_name), (p2_engine, p2_god_name) = match['p1_tuple'], match['p2_tuple']
        p1_god, p2_god = God[p1_god_name], God[p2_god_name]

        print(f"\nScheduling Matchup #{i + 1}: {match['Player 1']} vs {match['Player 2']}")

        shuffled_positions = random.sample(official_positions, len(official_positions))
        found_unplayed_pos_pair = False
        for template_pos in shuffled_positions:
            pos1 = prepare_position_string(template_pos, p1_god, p2_god)
            pos2 = reverse_pos(pos1)
            game1_tuple = (pos1, p1_engine, p2_engine, STARTING_TIME)
            game2_tuple = (pos2, p2_engine, p1_engine, STARTING_TIME)

            if game1_tuple not in played_matches and game2_tuple not in played_matches:
                print("  - Found unplayed position pair. Scheduling games.")
                games_to_play.append(
                    {'engine_g': p1_engine, 'engine_b': p2_engine, 'god_g': p1_god, 'god_b': p2_god, 'pos': pos1,
                     'starting_time': STARTING_TIME})
                games_to_play.append(
                    {'engine_g': p2_engine, 'engine_b': p1_engine, 'god_g': p2_god, 'god_b': p1_god, 'pos': pos2,
                     'starting_time': STARTING_TIME})
                found_unplayed_pos_pair = True
                break
        if not found_unplayed_pos_pair:
            print("  - SKIPPING: No unplayed starting position pairs found for this matchup.")

    if not games_to_play:
        print("\nNo new games were scheduled to play in this cycle.")
        return

    # Phase 3: Execute all scheduled games in parallel
    print(f"\n--- Playing {len(games_to_play)} games using up to {MAX_WORKERS} threads ---")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results_iterator = executor.map(play_game_worker, games_to_play)
        all_results = list(tqdm(results_iterator, total=len(games_to_play), desc="Playing games"))

    # Phase 4: Store all results in the database
    if all_results:
        print(f"\n--- Storing {len(all_results)} new match results in the database ---")
        conn = get_conn()
        cursor = conn.cursor()
        for result_data in tqdm(all_results, desc="Saving results"):
            store_match(cursor, **result_data)
        conn.commit()
        conn.close()
    print("\n--- Scheduled match session complete. ---")


def main(previous_elos: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Main function to run one cycle of the dynamic scheduler."""
    try:
        player_elos, player_total_games, opponent_spread = load_data_for_scheduler()
    except (ValueError, FileNotFoundError) as e:
        print(f"Error during data loading: {e}")
        return previous_elos

    print_elo_ranking_table(player_elos, previous_elos)

    schedule_df = score_matches(player_elos, player_total_games, opponent_spread)
    if schedule_df.empty:
        print("No valid matchups could be scored.")
        return player_elos.copy()

    print(f"\n--- Top {NUM_MATCHES_TO_SCHEDULE} Scheduled Matches ---")
    # MODIFIED: Added 'Elo Anomaly Score' to display
    display_cols = [
        'Player 1', 'Player 2', 'Total Score', 'Low Games Score',
        'Elo Close Score', 'Spread Score', 'Elo Anomaly Score'
    ]
    display_df = schedule_df[display_cols].head(NUM_MATCHES_TO_SCHEDULE).copy()
    for col in display_cols[2:]:
        display_df[col] = display_df[col].map('{:.4f}'.format)
    print(display_df.to_string())

    play_scheduled_matches(schedule_df)

    print("\nScheduler run finished. A new cycle will begin shortly.")
    return player_elos.copy()


if __name__ == "__main__":
    previous_elos_state = None
    while True:
        previous_elos_state = main(previous_elos_state)