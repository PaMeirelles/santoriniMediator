import sqlite3
import sys
import random
from game.board import Board
from database.models import God
from game.move import (
    ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove,
    HephaestusMove, HermesMove, MinotaurMove, PanMove, PrometheusMove, Move
)

# --- Configuration ---
DATABASE_FILE = "../../data/matches.db"  # IMPORTANT: Change this to the name of your database file

# --- God to Move Class Mapping ---
# This helps parse a move string into the correct Move object for a given god.
GOD_TO_MOVE_CLASS = {
    God.APOLLO: ApolloMove,
    God.ARTEMIS: ArtemisMove,
    God.ATHENA: AthenaMove,
    God.ATLAS: AtlasMove,
    God.DEMETER: DemeterMove,
    God.HEPHAESTUS: HephaestusMove,
    God.HERMES: HermesMove,
    God.MINOTAUR: MinotaurMove,
    God.PAN: PanMove,
    God.PROMETHEUS: PrometheusMove,
}


def parse_move_for_god(god: God, move_text: str) -> Move:
    """
    Parses a move string into the appropriate Move object based on the god.
    """
    move_class = GOD_TO_MOVE_CLASS.get(god)
    if not move_class:
        raise ValueError(f"Unknown or unsupported god for move parsing: {god}")
    return move_class.from_text(move_text)


def create_benchmark_table(cursor):
    """
    Creates the TB_BENCHMARK_POSITIONS table if it doesn't already exist.
    """
    try:
        cursor.execute("""
            CREATE TABLE "TB_BENCHMARK_POSITIONS" (
                "position" TEXT NOT NULL,
                PRIMARY KEY("position")
            )
        """)
        print("Table 'TB_BENCHMARK_POSITIONS' created successfully.")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print("Table 'TB_BENCHMARK_POSITIONS' already exists.")
        else:
            raise e


def select_and_insert_positions(conn):
    """
    Selects games, replays them to a mid-game state, and inserts the resulting
    position into the benchmark table, ensuring one position per matchup.
    """
    cursor = conn.cursor()

    # --- Selection Strategy ---
    # Fetch all games that have at least 10 moves (plies).
    query = """
        SELECT Starting_pos, Moves, God_G, God_B FROM TB_MATCHES
        WHERE Engine_G = 'Paladini_4.1.1_Mystic' 
        AND Engine_B = 'Paladini_4.1.1_Mystic'
    """

    cursor.execute(query)
    all_games_data = cursor.fetchall()

    if not all_games_data:
        print("No matches found meeting the criteria (at least 10 moves).")
        return

    # Group games by their god matchup
    games_by_matchup = {}
    for start_pos, moves_str, god_g, god_b in all_games_data:
        matchup = (god_g, god_b)
        if matchup not in games_by_matchup:
            games_by_matchup[matchup] = []
        games_by_matchup[matchup].append((start_pos, moves_str))

    print(f"Found {len(games_by_matchup)} unique god matchups to sample from.")

    positions_to_insert = set()
    processed_matchups = 0
    error_count = 0

    # Iterate through each matchup and find one valid position
    for _ in range(2):
        for matchup, games in games_by_matchup.items():
            random.shuffle(games)  # Randomize the order of games for this matchup
            position_found_for_matchup = False

            for start_pos, moves_str in games:
                try:
                    board = Board(start_pos)
                    all_moves = moves_str.strip().split()

                    max_ply = len(all_moves) - 10
                    if max_ply <= 0: continue
                    target_ply = random.randint(0, max_ply)

                    for i in range(target_ply):
                        move_text = all_moves[i]
                        current_god = board.gods[0] if board.turn == 1 else board.gods[1]
                        move_obj = parse_move_for_god(current_god, move_text)
                        board.make_move(move_obj)

                    mid_game_pos = board.position_to_text()
                    if mid_game_pos not in positions_to_insert:
                        positions_to_insert.add((mid_game_pos,))
                        position_found_for_matchup = True
                    break  # Success! Exit inner loop and move to the next matchup

                except (ValueError, IndexError, Exception) as e:
                    # This game failed, log it and the inner loop will try the next one.
                    error_count += 1
                    # Optional: uncomment to see errors for specific games
                    # print(f"Skipping a game for matchup {matchup} due to error: {e}", file=sys.stderr)
                    continue

            if position_found_for_matchup:
                processed_matchups += 1
            else:
                print(f"Warning: No valid mid-game position found for matchup {matchup} after trying all available games.",
                      file=sys.stderr)

    if not positions_to_insert:
        print("No valid mid-game positions could be generated.")
        return

    # --- Insertion ---
    insert_query = "INSERT OR IGNORE INTO TB_BENCHMARK_POSITIONS (position) VALUES (?)"
    cursor.executemany(insert_query, positions_to_insert)
    conn.commit()

    print("\n--- Process Complete ---")
    print(f"Successfully generated positions for: {processed_matchups} matchups.")
    print(f"Skipped games due to errors:        {error_count}")
    print(f"New rows added:                     {cursor.rowcount}")
    print(
        f"Total benchmark positions:          {cursor.execute('SELECT COUNT(*) FROM TB_BENCHMARK_POSITIONS').fetchone()[0]}")


def main():
    """
    Main function to run the script.
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        create_benchmark_table(cursor)
        select_and_insert_positions(conn)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except FileNotFoundError:
        print(f"Error: Database file '{DATABASE_FILE}' not found.")
        print("Please ensure DATABASE_FILE is set correctly.")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("\nDatabase connection closed.")


if __name__ == "__main__":
    main()

