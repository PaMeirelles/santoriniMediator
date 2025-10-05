# get_data.py
from typing import List, Tuple
import csv

from analysis.database import get_conn
# Assuming these imports are correct for your project structure
from client.controller import MOVE_CLASSES
from game.board import Board
from game.move import Move


def load_games():
    """Loads games from the database."""
    conn = get_conn()
    cursor = conn.cursor()
    # Using result = 1 for win, result = -1 for loss
    cursor.execute("""
        SELECT Moves, result, Starting_pos, God_G, God_B
        FROM TB_MATCHES
        WHERE (result = 1 OR result = -1) AND Moves IS NOT NULL 
        -- AND Engine_G = 'Paladini_7.1.1_Lunar' AND Engine_B = 'Paladini_7.1.1_Lunar'

    """)
    return cursor.fetchall()


# --- MODIFIED: This function now uses a manual ply counter ---
def get_positions_from_game(starting_pos: str, move_str: str) -> List[Tuple[str, int]]:
    """
    Generates all board positions that occurred in a game, along with their ply count,
    using a manual counter.
    """
    moves = move_str.split('\n')
    try:
        # Initialize the ply counter by parsing it from the starting position string.
        ply_counter = 0
        board = Board(starting_pos)
    except (IndexError, ValueError, Exception) as e:
        # Handle potential bad starting_pos data or parsing errors
        print(f"Skipping game due to board/ply init error: {e}")
        return []

    # The list will store tuples of (position_string, ply_count)
    positions: List[Tuple[str, int]] = [(board.position_to_text(), ply_counter)]

    gods = board.gods
    turn = 0
    for move_text in moves:
        if not move_text:
            continue
        god = gods[turn]
        move_cls = MOVE_CLASSES[god]
        move = move_cls.from_text(move_text)
        try:
            board.make_move(move)
            # Increment our manual counter after a successful move
            ply_counter += 1
            # Append the new position and the updated ply count
            positions.append((board.position_to_text(), ply_counter))
        except Exception as e:
            # A move might be invalid in the log, stop processing this game
            # print(f"Stopping game processing due to invalid move: {move_text} | Error: {e}")
            return positions
        turn = 1 - turn
    return positions


def create_training_data(output_file: str = 'training_data.csv'):
    """
    Processes games from DB and saves positions, plies, and results to a CSV file.
    Result is 1 if the first player won, 0 otherwise.
    """
    games = load_games()
    # The dataset will now include the ply count
    dataset: List[Tuple[str, int, int, str, str]] = []

    print(f"Processing {len(games)} games...")
    for moves, result, start_pos, god_g, god_b in games:
        # Normalize result: 1 for win, 0 for loss/draw
        game_result = 1 if result == 1 else 0

        # This now returns a list of (position, ply) tuples
        positions_with_plies = get_positions_from_game(start_pos, moves)

        for pos, ply in positions_with_plies:
            dataset.append((pos, ply, game_result, god_g, god_b))

    print(f"Generated {len(dataset)} total positions. Saving to {output_file}...")
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        # Add 'ply' to the header row
        writer.writerow(['position', 'ply', 'result', 'god_g', 'god_b'])
        writer.writerows(dataset)
    print("Done.")


if __name__ == '__main__':
    create_training_data()