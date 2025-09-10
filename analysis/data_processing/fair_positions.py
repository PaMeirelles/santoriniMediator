import itertools
import math
import random
import sqlite3

from analysis.database import get_conn

# --- User Configuration ---
# The greedy approach can handle much larger numbers than the original brute-force method.
NUM_TO_SELECT = 12


# --- Helper Functions ---
def to_xy(i):
    """Converts a board index (0-24) to (x, y) coordinates."""
    return i % 5, i // 5


def cpp_string_to_config(position_string):
    """Parses a 54-char C++ string to get worker positions."""
    g_workers, b_workers = [], []
    for i in range(25):
        worker_char = position_string[2 * i + 1]
        if worker_char == 'G':
            g_workers.append(i)
        elif worker_char == 'B':
            b_workers.append(i)
    return (tuple(sorted(g_workers)), tuple(sorted(b_workers)))


def load_positions_with_features(conn):
    """Loads all positions and their features from the database."""
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM TB_MATCHES')

    all_positions = []
    for row in cursor.fetchall():
        pos_string = row[0]
        features = list(row[1:])
        all_positions.append({
            "position_string": pos_string,
            "features": features,
            "config": cpp_string_to_config(pos_string)  # Also store the parsed format
        })
    print(f"Loaded {len(all_positions)} positions from the database.")
    return all_positions


# --- Diversity Selection Algorithm ---

def normalize_features(feature_vectors):
    """Normalizes each feature across all vectors to a [0, 1] range."""
    num_features = len(feature_vectors[0])
    min_vals, max_vals = [float('inf')] * num_features, [float('-inf')] * num_features
    for vec in feature_vectors:
        for i, val in enumerate(vec):
            min_vals[i], max_vals[i] = min(min_vals[i], val), max(max_vals[i], val)

    normalized_vectors = []
    for vec in feature_vectors:
        norm_vec = [(val - min_vals[i]) / (max_vals[i] - min_vals[i]) if max_vals[i] > min_vals[i] else 0.0 for i, val
                    in enumerate(vec)]
        normalized_vectors.append(norm_vec)
    return normalized_vectors


def select_diverse_set(all_positions, num_to_select):
    """
    Selects a diverse subset using a greedy algorithm, which is efficient for large sets.
    This approach iteratively selects the next item that is farthest from the already selected set.
    """
    if num_to_select >= len(all_positions):
        return all_positions

    # Extract the raw feature vectors from our loaded data
    feature_vectors = [pos["features"] for pos in all_positions]
    normalized_vectors = normalize_features(feature_vectors)
    vector_map = {i: vec for i, vec in enumerate(normalized_vectors)}

    # Weights correspond to: [Cohesion_G, Cohesion_B, Tension_Min, Tension_Avg, Control_Center]
    feature_weights = [1.0, 1.0, 1.0, 1.0, 2.0]

    # Pre-calculate all pairwise distances for efficiency
    dist_matrix = {}
    for i in range(len(all_positions)):
        for j in range(i, len(all_positions)):
            vec1, vec2 = vector_map[i], vector_map[j]
            weighted_squared_distance = sum(feature_weights[k] * (vec1[k] - vec2[k]) ** 2 for k in range(len(vec1)))
            dist = math.sqrt(weighted_squared_distance)
            dist_matrix[(i, j)] = dist_matrix[(j, i)] = dist

    # --- MODIFICATION START: Replaced Brute-Force with Greedy Algorithm ---
    print(f"Greedily selecting a diverse set of {num_to_select} positions...")

    all_indices = list(range(len(all_positions)))

    # 1. Initialization: Start with a random position to break symmetries.
    start_index = random.choice(all_indices)
    selected_indices = {start_index}
    remaining_indices = set(all_indices) - selected_indices

    # 2. Iterative Selection: Greedily add the most distant item in each step.
    while len(selected_indices) < num_to_select:
        best_next_index = -1
        max_min_dist_to_set = -1

        # For each candidate, find its minimum distance to the set of already selected items.
        for candidate_index in remaining_indices:
            # The distance from a candidate point to the selected set is the *minimum* of the distances
            # from the candidate to each point already in the set.
            dist_to_set = min(dist_matrix[(candidate_index, sel_idx)] for sel_idx in selected_indices)

            # We want to choose the candidate that has the largest such minimum distance.
            if dist_to_set > max_min_dist_to_set:
                max_min_dist_to_set = dist_to_set
                best_next_index = candidate_index

        # Add the best found candidate to our selected set and remove it from the remaining pool.
        if best_next_index != -1:
            selected_indices.add(best_next_index)
            remaining_indices.remove(best_next_index)
        else:
            # Should not happen in a normal case, but good for safety.
            break

    print("Greedy selection complete.")
    return [all_positions[i] for i in selected_indices]
    # --- MODIFICATION END ---


# --- Printing ---
def print_position_details(position_data, count, total):
    """Prints a visual representation of the board and its data."""
    config = position_data["config"]
    features = position_data["features"]
    cpp_string = position_data["position_string"]

    board = ['.'] * 25
    (g1, g2), (b1, b2) = config
    for i in [g1, g2]: board[i] = 'G'
    for i in [b1, b2]: board[i] = 'B'

    print(f"--- Position {count} of {total} ---")
    for i in range(5):
        print(" ".join(board[i * 5: i * 5 + 5]))

    print(f"\nString: {cpp_string}")
    print("Features:")
    print(f"  - Cohesion (G-G Dist): {features[0]:.2f}")
    print(f"  - Cohesion (B-B Dist): {features[1]:.2f}")
    print(f"  - Tension (Min G-B Dist): {features[2]:.2f}")
    print(f"  - Tension (Avg G-B Dist): {features[3]:.2f}")
    print(f"  - Board Control (Avg Dist from Center): {features[4]:.2f}\n")


# --- Main Execution ---
if __name__ == "__main__":
    conn = get_conn()
    try:
        all_positions_from_db = load_positions_with_features(conn)

        if NUM_TO_SELECT > len(all_positions_from_db):
            print(
                f"Error: Requested {NUM_TO_SELECT} positions, but only {len(all_positions_from_db)} are available in the database.")
        else:
            print(f"\nSelecting a diverse set of {NUM_TO_SELECT} positions (with weighted features)...")
            diverse_set = select_diverse_set(all_positions_from_db, NUM_TO_SELECT)

            print("\n--- Selected Diverse Set (Greedy Approach) ---")
            for i, pos_data in enumerate(diverse_set):
                print_position_details(pos_data, i + 1, len(diverse_set))

    except sqlite3.OperationalError as e:
        print(f"A database error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()