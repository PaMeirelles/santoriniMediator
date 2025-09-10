import itertools
import math
import random
import sqlite3

# --- Configuration ---
# Set the path to your desired database file
DB_PATH = r"../../data/matches.db"

# --- Constants and Board Helpers ---
POS_GAPS = [0, 1, 2, 1, 0, 1, 2, 3, 2, 1, 2, 3, 4, 3, 2, 1, 2, 3, 2, 1, 0, 1, 2, 1, 0]
BOARD_CENTER_IDX = 12


def to_xy(i):
    """Converts a board index (0-24) to (x, y) coordinates."""
    return (i % 5, i // 5)


def chebyshev_distance(i1, i2):
    """Calculates the Chebyshev (chessboard) distance between two indices."""
    x1, y1 = to_xy(i1)
    x2, y2 = to_xy(i2)
    return max(abs(x1 - x2), abs(y1 - y2))


# --- C++ String Conversion ---
def config_to_cpp_string(config):
    """Converts a board configuration into the 54-char C++ string format."""
    (g1, g2), (b1, b2) = config

    worker_map = ['N'] * 25
    worker_map[g1], worker_map[g2] = 'G', 'G'
    worker_map[b1], worker_map[b2] = 'B', 'B'

    board_part = "".join(['0' + worker for worker in worker_map])
    metadata_part = "0000"  # Turn=Gray, God1=None, God2=None, PreventUp=False
    return board_part + metadata_part


# --- Functions to Generate the Initial Set of Fair Positions ---
def check_distance_metric(workers_g, workers_b):
    g1, g2 = workers_g
    b1, b2 = workers_b
    min_dist_g = min(max(chebyshev_distance(g1, b1), chebyshev_distance(g1, b2)),
                     max(chebyshev_distance(g2, b1), chebyshev_distance(g2, b2)))
    min_dist_b = min(max(chebyshev_distance(b1, g1), chebyshev_distance(b1, g2)),
                     max(chebyshev_distance(b2, g1), chebyshev_distance(b2, g2)))
    return min_dist_g == min_dist_b


def get_symmetries(workers_g, workers_b):
    to_idx = lambda x, y: y * 5 + x
    symmetries = set()
    current_g, current_b = set(workers_g), set(workers_b)
    for _ in range(4):
        for flip in [False, True]:
            g_proc = {to_idx(x, 4 - y) if flip else i for i, (x, y) in ((i, to_xy(i)) for i in current_g)}
            b_proc = {to_idx(x, 4 - y) if flip else i for i, (x, y) in ((i, to_xy(i)) for i in current_b)}
            symmetries.add(tuple(sorted((tuple(sorted(g_proc)), tuple(sorted(b_proc))))))
        current_g = {to_idx(4 - y, x) for x, y in (to_xy(i) for i in current_g)}
        current_b = {to_idx(4 - y, x) for x, y in (to_xy(i) for i in current_b)}
    return symmetries


def generate_fair_positions():
    """Generates the full set of 557 fair positions based on previous logic."""
    print("Generating the initial pool of fair positions... (this may take a moment)")
    squares = list(range(25))
    canonical_forms = set()
    for four_squares in itertools.combinations(squares, 4):
        for g_workers in itertools.combinations(four_squares, 2):
            b_workers = tuple(sq for sq in four_squares if sq not in g_workers)
            score_g = POS_GAPS[g_workers[0]] + POS_GAPS[g_workers[1]]
            score_b = POS_GAPS[b_workers[0]] + POS_GAPS[b_workers[1]]
            # The filters that result in 557 positions
            if score_g == score_b and 3 <= score_g <= 6 and check_distance_metric(g_workers, b_workers):
                canonical_form = min(get_symmetries(g_workers, b_workers))
                canonical_forms.add(canonical_form)
    print(f"Generated {len(canonical_forms)} fair positions.")
    return sorted(list(canonical_forms))


# --- Feature Calculation ---
def calculate_feature_vector(config):
    """Calculates the strategic feature vector for a given board configuration."""
    (g1, g2), (b1, b2) = config
    dist_gg = float(chebyshev_distance(g1, g2))
    dist_bb = float(chebyshev_distance(b1, b2))
    inter_dists = [chebyshev_distance(g, b) for g in [g1, g2] for b in [b1, b2]]
    min_dist_gb = float(min(inter_dists))
    avg_dist_gb = sum(inter_dists) / 4.0
    avg_dist_center = sum(chebyshev_distance(w, BOARD_CENTER_IDX) for w in [g1, g2, b1, b2]) / 4.0
    return [dist_gg, dist_bb, min_dist_gb, avg_dist_gb, avg_dist_center]


# --- Database Interaction (following your reference style) ---

def get_conn(db_path=DB_PATH):
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(db_path)


def setup_database(conn):
    """Creates the DB table with the corrected schema."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS "TB_STARTING_POSITIONS"')
    cursor.execute("""
        CREATE TABLE "TB_STARTING_POSITIONS" (
            "Position_String"           TEXT NOT NULL PRIMARY KEY,
            "Cohesion_G"                REAL,
            "Cohesion_B"                REAL,
            "Tension_Min_Dist"          REAL,
            "Tension_Avg_Dist"          REAL,
            "Control_Avg_Dist_Center"   REAL
        )
    """)
    conn.commit()
    print(f"Database '{DB_PATH}' and table 'TB_STARTING_POSITIONS' are ready.")


def store_starting_position(cursor, cpp_string, features):
    """Inserts a single starting position and its features into the database."""
    data_to_insert = [cpp_string] + features
    cursor.execute("""
        INSERT INTO "TB_STARTING_POSITIONS" (
            "Position_String", "Cohesion_G", "Cohesion_B", 
            "Tension_Min_Dist", "Tension_Avg_Dist", "Control_Avg_Dist_Center"
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, data_to_insert)


# --- Main Execution ---
if __name__ == "__main__":
    all_fair_positions = generate_fair_positions()

    conn = get_conn()
    try:
        setup_database(conn)
        cursor = conn.cursor()

        print(f"\nPopulating database with {len(all_fair_positions)} positions...")

        for config in all_fair_positions:
            features = calculate_feature_vector(config)
            cpp_string = config_to_cpp_string(config)
            store_starting_position(cursor, cpp_string, features)

        conn.commit()
        print(f"\n--- Success! Database '{DB_PATH}' created and populated. ---")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()