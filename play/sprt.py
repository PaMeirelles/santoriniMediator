import concurrent.futures
import math
from typing import Tuple, Dict
from collections import defaultdict

from analysis.database import get_conn, store_match
from database.models import God, string_to_god, GameParams
from helpers import load_official_positions, play_game_worker, load_historical_results, get_played_matches
from play.helpers import prepare_position_string

POSITIONS_FILE_PATH = "../data/official_starting_pos.txt"
MAX_WORKERS = 9

ALPHA = 0.05  # Probability of accepting H1 when H0 is true (Type I error)
BETA = 0.05  # Probability of accepting H0 when H1 is true (Type II error)


def update_stats(
        game_score: float,
        wins: int,
        losses: int,
        stats_per_god: defaultdict,
        stats_as_gray: Dict,
        stats_as_blue: Dict,
        god_played: God,
        engine_g: str,
        new_engine: str
) -> Tuple[int, int]:
    """Updates all relevant statistics based on a single game result."""
    if game_score == 1.0:
        wins += 1
        stats_per_god[god_played]['wins'] += 1
        if engine_g == new_engine:
            stats_as_gray['wins'] += 1
        else:  # new_engine was blue
            stats_as_blue['wins'] += 1

    elif game_score == 0.0:
        losses += 1
        stats_per_god[god_played]['losses'] += 1
        if engine_g == new_engine:
            stats_as_gray['losses'] += 1
        else:  # new_engine was blue
            stats_as_blue['losses'] += 1
    else:
        raise ValueError("Game score must be 1.0 or 0.0")

    return wins, losses

def result_to_score(result: int, engine_g: str, pov_engine: str) -> int:
    if engine_g == pov_engine:
        return result > 0
    return result < 0


def calculate_a_and_b(alpha: float, beta: float) -> Tuple[float, float]:
    """Calculates the lower and upper stopping boundaries (a, b) for SPRT."""
    a = math.log(beta / (1 - alpha))
    b = math.log((1 - beta) / alpha)
    return a, b


def update_s(old_s: float, game_score: float, expected_elo_change: float) -> float:
    """Updates the log-likelihood ratio score 's' based on a single game result."""
    # Probability of winning for the new engine under H1 (elo advantage)
    p1 = 1.0 / (1.0 + 10.0 ** (-expected_elo_change / 400.0))
    # Probability of winning under H0 (equal elo)
    p0 = 0.5

    # Calculate the log-likelihood ratio for the game's score (1 for win, 0 for loss)
    llr = game_score * math.log(p1 / p0) + (1 - game_score) * math.log((1 - p1) / (1 - p0))

    return old_s + llr


def print_sprt_report(wins, total_games_played, stats_as_gray, stats_as_blue,
                      stats_per_god, s, a, b, new_engine, old_engine):
    """Prints the detailed final report of the SPRT test."""
    print("\n--- Detailed Report ---")

    # Overall Winrate
    overall_winrate = (wins / total_games_played) * 100 if total_games_played > 0 else 0
    print(f"Overall Winrate : {overall_winrate:.2f}% ({wins}/{total_games_played})")

    # Winrate by Color
    gray_games = stats_as_gray['wins'] + stats_as_gray['losses']
    gray_winrate = (stats_as_gray['wins'] / gray_games) * 100 if gray_games > 0 else 0
    print(f"Winrate as gray : {gray_winrate:.2f}% ({stats_as_gray['wins']}/{gray_games})")

    blue_games = stats_as_blue['wins'] + stats_as_blue['losses']
    blue_winrate = (stats_as_blue['wins'] / blue_games) * 100 if blue_games > 0 else 0
    print(f"Winrate as Blue : {blue_winrate:.2f}% ({stats_as_blue['wins']}/{blue_games})")

    # Winrate per God
    print("\n--- Winrate per God ---")
    sorted_gods = sorted(stats_per_god.items(), key=lambda item: item[0].value)
    for god, stats in sorted_gods:
        god_games = stats['wins'] + stats['losses']
        winrate = (stats['wins'] / god_games) * 100 if god_games > 0 else 0
        print(f"{god.name:<12}: {winrate:.2f}% ({stats['wins']}/{god_games})")

    print("\n--- Final Conclusion ---")

    if s >= b:
        print(f"Result: H1 accepted. '{new_engine}' is likely stronger than '{old_engine}'.")
    elif s <= a:  # s <= a
        print(f"Result: H0 accepted. '{new_engine}' is not demonstrably stronger than '{old_engine}'.")
    else:
        print("We ran out of games. No conclusion.")


def sprt(old_engine: str, new_engine: str, time_control: int, expected_elo_change: int):
    positions = load_official_positions(POSITIONS_FILE_PATH)
    a, b = calculate_a_and_b(ALPHA, BETA)
    max_workers = MAX_WORKERS
    s = 0.0
    position_index = 0

    total_games_played = 0
    wins = 0
    losses = 0

    stats_per_god = defaultdict(lambda: {'wins': 0, 'losses': 0})
    stats_as_gray = {'wins': 0, 'losses': 0}
    stats_as_blue = {'wins': 0, 'losses': 0}

    print(f"--- Starting SPRT: '{new_engine}' vs '{old_engine}' ---")
    print(f"H0: elo_diff = 0, H1: elo_diff = {expected_elo_change}")
    print(f"Boundaries: a = {a:.3f}, b = {b:.3f}\n")

    conn = get_conn()
    cursor = conn.cursor()

    historical_results = load_historical_results(cursor, old_engine, new_engine, time_control)
    if historical_results:
        print(f"Found {len(historical_results)} historical games. Re-calculating state...")
        for match in historical_results:
            game_score = result_to_score(match['Result'], match['Engine_G'], new_engine)

            total_games_played += 1
            god_played = string_to_god(match['God_G'])

            wins, losses = update_stats(
                game_score, wins, losses, stats_per_god, stats_as_gray, stats_as_blue,
                god_played, match['Engine_G'], new_engine
            )
            s = update_s(s, game_score, expected_elo_change)

        score_pct = (wins / total_games_played) * 100 if total_games_played > 0 else 0.0
        print(f"Resumed state: Games={total_games_played} | Score: +{wins} -{losses} ({score_pct:.2f}%)")
        print(f"SPRT: s = {s:.3f} [a={a:.3f}, b={b:.3f}]\n")

    played_matches_set = get_played_matches(cursor)
    conn.close()

    while a < s < b and position_index < len(positions):
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            template_pos = positions[position_index]
            position_index += 1

            games_to_play = []
            for god in God:
                if god == God.ATHENA: continue
                pos = prepare_position_string(template_pos, god, god)

                # Game 1: new_engine as Gray
                match_tuple1 = (pos, new_engine, old_engine, time_control)
                if match_tuple1 not in played_matches_set:
                    games_to_play.append(GameParams(new_engine, old_engine, time_control, time_control, god, god, pos))

                # Game 2: new_engine as Blue
                match_tuple2 = (pos, old_engine, new_engine, time_control)
                if match_tuple2 not in played_matches_set:
                    games_to_play.append(GameParams(old_engine, new_engine, time_control, time_control, god, god, pos))

            if not games_to_play:
                print(f"All games for position {position_index - 1} already played. Skipping.")
                continue

            results_iterator = executor.map(play_game_worker, games_to_play)
            results = list(results_iterator)

            conn = get_conn()
            cursor = conn.cursor()
            for result_data in results:
                params, result = result_data
                store_match(cursor,
                            params.god_g,
                            params.god_b,
                            params.engine_g,
                            params.engine_b,
                            result.result,
                            params.time_g,
                            result.moves,
                            params.position_str)

                game_score = result_to_score(result.result, params.engine_g, new_engine)

                # Update stats
                total_games_played += 1
                god_played = params.god_g  # Since god_g and god_b are the same

                wins, losses = update_stats(
                    game_score, wins, losses, stats_per_god, stats_as_gray, stats_as_blue,
                    god_played, params.engine_g, new_engine
                )

                # Update the SPRT log-likelihood score
                s = update_s(s, game_score, expected_elo_change)

            conn.commit()
            conn.close()

            # Print a progress report after each batch of games
            score_pct = (wins / total_games_played) * 100 if total_games_played > 0 else 0.0
            print(f"Games: {total_games_played} | Score: +{wins} -{losses} ({score_pct:.2f}%)")
            print(f"SPRT: s = {s:.3f} [a={a:.3f}, b={b:.3f}]\n")

    # The loop has terminated, so a boundary was crossed. Announce the final result.
    print("--- SPRT test finished ---")
    print(f"Final Score: +{wins} -{losses} over {total_games_played} games.")

    print_sprt_report(wins, total_games_played, stats_as_gray, stats_as_blue,
                      stats_per_god, s, a, b, new_engine, old_engine)


if __name__ == "__main__":
    old_engine = "Paladini_8.1.8_Firefly"
    new_engines = [
        "Paladini_9.1.1_Prophet"
    ]

    expected_elo_change = 25
    for engine in new_engines:
        sprt(old_engine, engine, 60, expected_elo_change)
