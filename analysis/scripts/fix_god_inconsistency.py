import sqlite3

from database.models import god_to_string, God


def fix_sqlite_god_inconsistencies(db_path: str):
    """
    Iterates through TB_MATCHES, parses the true gods from the 54-char
    starting_pos string, and fixes the God_G and God_B columns.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fetch only matches that have a starting position
    cursor.execute("SELECT Id, Starting_pos FROM TB_MATCHES WHERE Starting_pos IS NOT NULL")
    rows = cursor.fetchall()

    updates = []
    error_count = 0

    for match_id, starting_pos in rows:
        if len(starting_pos) >= 53:
            try:
                # In board.py: position[51] is Gray's God, position[52] is Blue's God
                god_g_int = int(starting_pos[51])
                god_b_int = int(starting_pos[52])

                # Convert the integers to your Enum, then to the string your DB expects
                true_god_g_str = god_to_string(God(god_g_int))
                true_god_b_str = god_to_string(God(god_b_int))

                updates.append((true_god_g_str, true_god_b_str, match_id))
            except ValueError as e:
                print(f"Skipping match {match_id}: Invalid god index ({e})")
                error_count += 1
            except Exception as e:
                print(f"Skipping match {match_id} due to unexpected error: {e}")
                error_count += 1
        else:
            print(f"Skipping match {match_id}: starting_pos string too short ({len(starting_pos)} chars)")
            error_count += 1

    # Execute the batch update
    if updates:
        cursor.executemany(
            "UPDATE TB_MATCHES SET God_G = ?, God_B = ? WHERE Id = ?",
            updates
        )
        conn.commit()
        print(f"Success: Updated {len(updates)} match records.")
    else:
        print("No valid updates found.")

    if error_count > 0:
        print(f"Finished with {error_count} skipped rows.")

    conn.close()


if __name__ == "__main__":
    # Update the path if you are running this outside of your mediator root
    DB_PATH = r"C:\Users\rafae\PycharmProjects\santoriniMediator\data\matches.db"

    # Run the throwaway fix
    fix_sqlite_god_inconsistencies(DB_PATH)