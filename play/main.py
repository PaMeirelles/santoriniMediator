import traceback
from game.board import God
from analysis.database import get_conn, store_match
from play.manager import run_match


def main():
    """
    Sets up and runs a single game match, stores the result in the database,
    and ensures the database connection is properly closed.
    """
    # --- Match Configuration ---
    time_control = 60 * 10
    engine_b = "Paladini_7.1_Spirit"
    engine_a = "human"
    god_a = God.APOLLO
    god_b = God.ATHENA
    # Initial board position string. run_match is assumed to prepend god info.
    initial_pos = "0N0N0N0N0N0N0N0B0N0N0N0N0G0G0N0N0N0B0N0N0N0N0N0N0N0020"

    conn = None  # Initialize connection to None
    try:
        # Establish the database connection
        conn = get_conn()
        cursor = conn.cursor()

        print(f"Starting match: {engine_a} ({god_a.name}) vs. {engine_b} ({god_b.name})")

        # Run the match
        match_result = run_match(cursor, engine_a, engine_b, god_a, god_b, time_control, initial_pos, headless=False)

        print("Match finished. Storing result...")

        # Store the match result in the database
        store_match(cursor, god_a, god_b, engine_a, engine_b, match_result, time_control, "", initial_pos)

        # Commit the transaction to save changes
        conn.commit()
        print("Result stored successfully.")

    except Exception as e:
        print(f"An error occurred during the match: {e}")
        traceback.print_exc()
        # If an error occurs, roll back any partial database changes
        if conn:
            conn.rollback()

    finally:
        # This block ensures the connection is closed even if errors occurred
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    main()