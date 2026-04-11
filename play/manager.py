# play/manager.py

import random
import time
from typing import Optional, List

from database.models import God
from analysis.database import get_conn, store_match
from game.constants import ENGINES
from client.controller import Controller


# --- Helper functions for loading and preparing positions ---

def load_official_positions(file_path: str) -> List[str]:
    """Loads a list of starting position templates from a file."""
    try:
        with open(file_path, 'r') as f:
            # Return only non-empty lines
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Starting positions file not found at '{file_path}'.")
        return []


def prepare_position_string(template_pos: str, god_g: God, god_b: God) -> str:
    """Injects the correct God IDs into a template position string."""
    # The god IDs are at indices 51 and 52 in the 54-char string.
    god_g_char = str(god_g.value)
    god_b_char = str(god_b.value)
    return template_pos[:51] + god_g_char + god_b_char + template_pos[53:]


# --- The Corrected Position Fetching Logic ---

def fetch_unplayed_position_from_file(
        cursor, god_a: God, god_b: God,
        engine_a: str, engine_b: str
) -> Optional[str]:
    """
    Selects a random, unplayed starting position from the official text file
    for a given engine matchup.
    """
    # 1. Load all possible starting position templates from the text file.
    #    We assume the file is in the standard data directory.
    templates = load_official_positions("../data/official_starting_pos.txt")
    if not templates:
        return None  # No templates found, can't select a position.

    # 2. Find all starting positions already played by this specific engine pair.
    #    The query checks for both (a vs b) and (b vs a).
    cursor.execute("""
        SELECT DISTINCT Starting_pos FROM TB_MATCHES
        WHERE (Engine_G = ? AND Engine_B = ?)
           OR (Engine_G = ? AND Engine_B = ?)
    """, (engine_a, engine_b, engine_b, engine_a))

    played_positions = {row[0] for row in cursor.fetchall()}

    # 3. Determine which templates are still available to be played.
    #    We check if any position starting with a given template has been played.
    #    This is a simplification; a more robust check would ignore the god part of the string.
    unplayed_templates = [
        t for t in templates
        if not any(p.startswith(t[:51]) for p in played_positions)
    ]

    # 4. If there are unplayed templates, pick one randomly.
    if not unplayed_templates:
        # If all official positions have been played, fall back to re-using a random one.
        print("Warning: All official starting positions have been used for this engine pair. Re-using a position.")
        selected_template = random.choice(templates)
    else:
        selected_template = random.choice(unplayed_templates)

    # 5. Inject the correct gods for the current matchup into the template.
    return prepare_position_string(selected_template, god_a, god_b)


# --- Functions from the original manager.py that are still needed ---

def run_match(
        cursor,
        engine_name_g: str,
        engine_name_b: str,
        god_a: God,
        god_b: God,
        starting_time: int,
        pos: str,
        headless: bool = True
):
    """Runs a single match and stores the result."""
    ctrl = Controller(
        pos, starting_time, starting_time,
        ENGINES[engine_name_g],
        ENGINES[engine_name_b],
        headless=headless
    )
    result, moves = ctrl.run_game()
    store_match(
        cursor.connection,  # Pass the connection object for committing
        god_a, god_b, engine_name_g, engine_name_b,
        result, starting_time, moves, pos
    )
    return result


# We keep this function as a wrapper, but change what it calls.
def fetch_position(
        cursor, god_a: God, god_b: God,
        engine_a: str, engine_b: str,
        central: bool = False  # The 'central' flag is now ignored but kept for compatibility
) -> Optional[str]:
    """Wrapper function to fetch a starting position."""
    return fetch_unplayed_position_from_file(
        cursor, god_a, god_b, engine_a, engine_b
    )