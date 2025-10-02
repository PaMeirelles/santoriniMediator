# tune.py
import numpy as np
import pandas as pd
import multiprocessing
from itertools import repeat
from copy import deepcopy

# Import the updated evaluation logic, Parameters class, and Board class
from evaluation import score_position, Parameters, FIXED_PARAMS
from game.board import Board

# K value found from previous tuning step
K = 0.003150

# --- MODIFIED: Optimization Configuration ---

# Number of full passes to make over all parameters
NUM_CYCLES = 500

# --- ADDED: List of Gods ---
# Define the gods you want to create specific tuning parameters for.
# The names should match the values in your 'god_g' and 'god_b' columns.
GOD_LIST = [
    'APOLLO', 'ARTEMIS', 'ATHENA', 'ATLAS', 'DEMETER',
    'HEPHAESTUS', 'MINOTAUR', 'PAN', 'PROMETHEUS', 'HERMES'
]

# Define the full set of parameters to tune, with their search steps.
PARAM_SEARCH_CONFIG = {
    'centrality_gap': {'step': 5},
    'h2_gap': {'step': 5},
    # Height 0
    'sh0_mult': {'step': 5},
    'sh0_power': {'step': 0.05},
    'nh0_mult': {'step': 5},
    'nh0_power': {'step': 0.05},
    'nn0_mult': {'step': 5},
    'nn0_power': {'step': 0.05},
    # Height 1
    'sh1_mult': {'step': 5},
    'sh1_power': {'step': 0.05},
    'nh1_mult': {'step': 5},
    'nh1_power': {'step': 0.05},
    'ph1_mult': {'step': 5},
    'ph1_power': {'step': 0.05},
    'nn1_mult': {'step': 5},
    'nn1_power': {'step': 0.05},
    # Height 2
    'sh2_mult': {'step': 5},
    'sh2_power': {'step': 0.05},
    'nh2_mult': {'step': 5},
    'nh2_power': {'step': 0.05},
    'ph2_mult': {'step': 5},
    'ph2_power': {'step': 0.05},
    # --- ADDED: Tempo and God Parameters ---
    'tempo_bonus': {'step': 5},
}

# Dynamically add god parameters to the search configuration
for god in GOD_LIST:
    param_name = f'god_{god}_bonus'
    PARAM_SEARCH_CONFIG[param_name] = {'step': 10}


# --- Helper Functions (Sigmoid is Unchanged) ---

def sigmoid(score):
    """Maps an evaluation score to a win probability (0 to 1)."""
    return 1 / (1 + np.exp(-K * score))


# --- MODIFIED: Objective and Worker Functions ---

def objective_function(params_obj, positions, tempos, gods_g, gods_b, results):
    """
    Calculates the Mean Squared Error for a given set of parameters.
    This is the function we want to minimize.
    """
    # Pass the new features to the worker function
    scores = pool.starmap(evaluate_single_position, zip(positions, tempos, gods_g, gods_b, repeat(params_obj)))
    predicted_probs = sigmoid(np.array(scores))
    mse = np.mean((predicted_probs - results) ** 2)
    return mse


def evaluate_single_position(pos_text, tempo, god_g, god_b, params_obj):
    """Worker function to evaluate a single board position."""
    board = Board(pos_text)
    # Pass new features to the main scoring function
    return score_position(board, params=params_obj, tempo=tempo, god_g=god_g, god_b=god_b)


def pretty_print_params(params_dict):
    """Prints the parameter dictionary in a readable format."""
    print("  Optimized Parameters:")
    # Separate god params for cleaner printing
    god_params = {k: v for k, v in params_dict.items() if k.startswith('god_')}
    other_params = {k: v for k, v in params_dict.items() if not k.startswith('god_')}

    for key, value in sorted(other_params.items()):
        if isinstance(value, float):
            print(f"    {key}: {value:.4f}")
        else:
            print(f"    {key}: {value}")

    print("\n    --- God Bonuses ---")
    for key, value in sorted(god_params.items()):
        print(f"    {key}: {value}")


# --- Main Execution ---

if __name__ == '__main__':
    # 1. --- MODIFIED: Load the training data ---
    print("Loading training data...")
    try:
        df = pd.read_csv('training_data.csv')
    except FileNotFoundError:
        print("Error: 'training_data.csv' not found. Please generate it first.")
        exit()

    positions = df['position'].tolist()

    plies = df['ply'].to_numpy()
    tempos = ['g' if p % 2 == 0 else 'b' for p in plies]

    gods_g = df['god_g'].tolist()
    gods_b = df['god_b'].tolist()
    results = df['result'].to_numpy()
    print(f"Loaded and processed {len(positions)} positions.")

    current_params = {
        'centrality_gap': FIXED_PARAMS.posScore[1],
        'h2_gap': FIXED_PARAMS.heightScore[2] - 100,
        # Height 0-2 params (unchanged)
        'sh0_mult': FIXED_PARAMS.sh0_mult, 'sh0_power': FIXED_PARAMS.sh0_power,
        'nh0_mult': FIXED_PARAMS.nh0_mult, 'nh0_power': FIXED_PARAMS.nh0_power,
        'nn0_mult': FIXED_PARAMS.nn0_mult, 'nn0_power': FIXED_PARAMS.nn0_power,
        'sh1_mult': FIXED_PARAMS.sh1_mult, 'sh1_power': FIXED_PARAMS.sh1_power,
        'nh1_mult': FIXED_PARAMS.nh1_mult, 'nh1_power': FIXED_PARAMS.nh1_power,
        'ph1_mult': FIXED_PARAMS.ph1_mult, 'ph1_power': FIXED_PARAMS.ph1_power,
        'nn1_mult': FIXED_PARAMS.nn1_mult, 'nn1_power': FIXED_PARAMS.nn1_power,
        'sh2_mult': FIXED_PARAMS.sh2_mult, 'sh2_power': FIXED_PARAMS.sh2_power,
        'nh2_mult': FIXED_PARAMS.nh2_mult, 'nh2_power': FIXED_PARAMS.nh2_power,
        'ph2_mult': FIXED_PARAMS.ph2_mult, 'ph2_power': FIXED_PARAMS.ph2_power,

        'tempo_bonus': FIXED_PARAMS.tempo_bonus,
    }
    for god in GOD_LIST:
        current_params[f'god_{god}_bonus'] = FIXED_PARAMS.god_bonuses[god.lower()]

    # 3. Start the optimization process
    with multiprocessing.Pool() as pool:
        print(f"\nStarting optimization with {pool._processes} worker processes...")

        # Calculate the initial error with the starting parameters
        best_mse = objective_function(Parameters(**current_params), positions, tempos, gods_g, gods_b, results)
        print(f"Initial MSE: {best_mse:.12f}")
        pretty_print_params(current_params)

        # Main optimization loop (Coordinate Ascent)
        for cycle in range(NUM_CYCLES):
            print(f"\n--- Starting Optimization Cycle {cycle + 1}/{NUM_CYCLES} ---")
            improved_in_cycle = False

            # Iterate through each parameter to tune it individually
            for param_name, config in PARAM_SEARCH_CONFIG.items():
                # Test nudging the parameter up and down
                for direction in [-1, 1]:
                    test_params = deepcopy(current_params)
                    step = config['step']
                    test_params[param_name] += direction * step

                    mse = objective_function(Parameters(**test_params), positions, tempos, gods_g, gods_b, results)

                    # If this change is an improvement, keep it
                    if mse < best_mse:
                        best_mse = mse
                        current_params = test_params
                        improved_in_cycle = True

                        # Print improvement
                        val = current_params[param_name]
                        val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
                        print(f"  Improvement for '{param_name}': {val_str} (MSE: {best_mse:.12f})")

            if not improved_in_cycle:
                print("\nNo improvement in the last cycle. Stopping optimization.")
                break

    # 4. Print the final results
    print("\n--- Optimization Finished ---")
    print(f"Final Best Mean Squared Error: {best_mse:.12f}")
    pretty_print_params(current_params)