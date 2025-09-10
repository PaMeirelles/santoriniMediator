# play/smart_scheduler.py

import itertools
import time
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

# Import the Bradley-Terry calculation from your analysis script
from analysis.visualization.visualization import calculate_bradley_terry_multiple

# Project imports
# MODIFIED: Added prepare_position_string to the import
from analysis.database import get_conn, store_match
from play.manager import fetch_position, prepare_position_string
from client.controller import Controller
from game.board import God
from game.constants import ENGINES


@dataclass(frozen=True)
class BradleyTerryRating:
    """Represents the output of the Bradley-Terry model for a player."""
    rating: float  # The global strength parameter
    se: float  # The standard error of the rating (uncertainty)


@dataclass(frozen=True, eq=True, unsafe_hash=True)
class Player:
    """A simple dataclass to represent a (God, Engine) pair."""
    god: str
    engine: str


def calculate_bradley_terry_ratings(matches_df: pd.DataFrame) -> Dict[Player, BradleyTerryRating]:
    """
    Calculates global Bradley-Terry ratings for all players.
    """
    print(f"Calculating global Bradley-Terry ratings from {len(matches_df)} matches...")
    available_engines = set(ENGINES.keys())

    # Filter for matches between currently available engines
    filtered_df = matches_df[
        matches_df['Engine_G'].isin(available_engines) &
        matches_df['Engine_B'].isin(available_engines)
        ].copy()

    if filtered_df.empty:
        print("No matches found for available engines. Cannot calculate ratings.")
        return {}

    bt_summary_df = calculate_bradley_terry_multiple(list(available_engines))

    if bt_summary_df.empty:
        print("Bradley-Terry calculation returned no results.")
        return {}

    # Convert the resulting DataFrame into the desired ratings dictionary
    ratings = {}
    for index, row in bt_summary_df.iterrows():
        try:
            god, engine = index.split('@')
            player = Player(god=god, engine=engine)
            ratings[player] = BradleyTerryRating(rating=row['Rating'], se=row['SE'])
        except ValueError:
            print(f"Warning: Could not parse player from BT index '{index}'")
            continue

    print("Bradley-Terry ratings calculated successfully.")
    return ratings


def run_matchup_set(p1: Player, p2: Player, starting_time: int):
    """
    MODIFIED: Runs a fair, symmetric game set for the given player matchup,
    preserving the (god, engine) pairings by swapping sides on a
    symmetrically mirrored board.
    """
    conn = get_conn()
    cursor = conn.cursor()

    p1_god, p2_god = God[p1.god], God[p2.god]
    p1_engine, p2_engine = p1.engine, p2.engine

    # --- GAME 1: p1 (Gray) vs p2 (Blue) ---
    # Find a position where p1's god is Gray and p2's god is Blue
    pos1 = fetch_position(cursor, p1_god, p2_god, p1_engine, p2_engine, central=True)
    if not pos1:
        print(f"No unplayed positions for {p1_engine}({p1_god.name}) vs {p2_engine}({p2_god.name}). Skipping matchup.")
        conn.close()
        return

    print(f"-> Game 1: {p1_engine}({p1_god.name}) [Gray] vs {p2_engine}({p2_god.name}) [Blue]")
    ctrl1 = Controller(pos1, starting_time, starting_time, ENGINES[p1_engine], ENGINES[p2_engine], headless=True)
    result1, moves1 = ctrl1.run_game()
    store_match(cursor.connection, p1_god, p2_god, p1_engine, p2_engine, result1, starting_time, moves1, pos1)

    # --- GAME 2: p2 (Gray) vs p1 (Blue) on a mirrored board ---
    # Create a new position string with the gods swapped to ensure symmetry.
    # This preserves the god-engine pairings while swapping sides.
    template = pos1[:51] + '00' + pos1[53:]  # Extract board layout from the first game
    pos2 = prepare_position_string(template, p2_god, p1_god)  # p2's god is now Gray

    print(f"-> Game 2: {p2_engine}({p2_god.name}) [Gray] vs {p1_engine}({p1_god.name}) [Blue]")
    # Controller expects (..., engine_gray, engine_blue, ...)
    ctrl2 = Controller(pos2, starting_time, starting_time, ENGINES[p2_engine], ENGINES[p1_engine], headless=True)
    result2, moves2 = ctrl2.run_game()
    # store_match expects (..., god_gray, god_blue, engine_gray, engine_blue, ...)
    store_match(cursor.connection, p2_god, p1_god, p2_engine, p1_engine, result2, starting_time, moves2, pos2)

    conn.commit()
    conn.close()


def print_ratings_table(ratings: Dict[Player, BradleyTerryRating]):
    """Prints a sorted table based on Bradley-Terry ratings."""
    if not ratings:
        print("No ratings to display.")
        return

    records = []
    for p, r in ratings.items():
        conservative_rating = r.rating - 2 * r.se
        records.append({
            "Engine": p.engine,
            "God": p.god,
            "BT Rating": r.rating,
            "Std Error (SE)": r.se,
            "Conservative Rating": conservative_rating
        })

    df = pd.DataFrame(records)
    df = df.sort_values(by="Conservative Rating", ascending=False).reset_index(drop=True)
    df.index += 1  # Start rank at 1

    print("\n--- Current Player Ratings (BT Rating - 2*SE) ---")
    print(df.to_string(formatters={
        'BT Rating': '{:,.2f}'.format,
        'Std Error (SE)': '{:,.2f}'.format,
        'Conservative Rating': '{:,.2f}'.format
    }))
    return df


def main_scheduler_loop(starting_time: int = 60):
    """
    Runs a ladder-based scheduler using Bradley-Terry ratings.
    In each cycle, it recalculates global BT ratings for all engine-god pairs,
    creates a ranked ladder, and then schedules matches between adjacent
    players on that ladder.
    """
    while True:
        print("\n" + "=" * 50)
        print("--- Running BT Ladder Scheduler Cycle ---")
        print(f"Timestamp: {pd.Timestamp.now()}")
        print("=" * 50)

        # 1. Fetch ALL historical data for a global rating calculation.
        print("\nFetching all match data for global rating calculation...")
        conn = get_conn()
        full_df = pd.read_sql_query("SELECT * FROM TB_MATCHES ORDER BY Id ASC", conn)
        conn.close()

        if full_df.empty:
            print("Database is empty. Waiting for games to be played.")
            time.sleep(60)
            continue

        # 2. Calculate global Bradley-Terry ratings for all players.
        ratings = calculate_bradley_terry_ratings(full_df)

        # 3. Print the ratings leaderboard.
        ratings_df = print_ratings_table(ratings)

        # 4. Create a sorted ladder of players based on the ratings table.
        if ratings_df is None or ratings_df.empty:
            print("No ratings available to create a ladder. Waiting...")
            time.sleep(60)
            continue

        player_ladder = [Player(god=row['God'], engine=row['Engine']) for _, row in ratings_df.iterrows()]

        # --- Pairing Logic ---
        print("\n--- Pairing Players for Matches ---")
        unpaired_players = set(player_ladder)
        matches_to_play = []

        # Iterate through the ladder to find a partner for each player
        for i, p1 in enumerate(player_ladder):
            # If p1 is already paired, skip it
            if p1 not in unpaired_players:
                continue

            # Find the closest, available, non-mirror opponent for p1
            found_opponent = None
            opponent_rank = -1
            for j in range(i + 1, len(player_ladder)):
                p2 = player_ladder[j]
                if p2 in unpaired_players and p1.god != p2.god:
                    found_opponent = p2
                    opponent_rank = j + 1
                    break  # Found the best partner for p1

            if found_opponent:
                matches_to_play.append((p1, found_opponent, i + 1, opponent_rank))
                unpaired_players.remove(p1)
                unpaired_players.remove(found_opponent)

        # 5. Execute the scheduled matchups
        if not matches_to_play:
            print("No valid non-mirror pairings could be made in this cycle.")
        else:
            print(f"\n--- Scheduling {len(matches_to_play)} Matches ---")
            for p1, p2, rank1, rank2 in matches_to_play:
                print(f"\n[PLAY] Matchup: #{rank1} {p1.engine}({p1.god}) vs. #{rank2} {p2.engine}({p2.god})")
                run_matchup_set(p1, p2, starting_time)
                time.sleep(0.5)

        if unpaired_players:
            print("\n--- Unpaired Players This Cycle ---")
            for p in unpaired_players:
                print(f"- {p.engine}({p.god})")
        # --- End of Pairing Logic ---

        print("\n--- Cycle Complete ---")
        print("Pausing for 5 minutes before starting the next cycle...")
        time.sleep(300)


if __name__ == "__main__":
    try:
        main_scheduler_loop()
    except KeyboardInterrupt:
        print("\nScheduler stopped by user.")