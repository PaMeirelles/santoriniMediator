# tune.py
import numpy as np
import pandas as pd
import multiprocessing
from itertools import repeat
from copy import deepcopy

# Import the updated evaluation logic, Parameters class, and the fixed values dictionary
from evaluation import score_position, Parameters, FIXED_PARAMS, FIXED_PARAM_VALUES
from game.board import Board

# Initial K value (will be tuned)
K = 0.002770

# --- Optimization Configuration ---
NUM_CYCLES = 500

# List of Gods
GOD_LIST = [
    'APOLLO', 'ARTEMIS', 'ATHENA', 'ATLAS', 'DEMETER',
    'HEPHAESTUS', 'MINOTAUR', 'PAN', 'PROMETHEUS', 'HERMES'
]

# Define the full set of parameters to tune, with their search steps.
PARAM_SEARCH_CONFIG = {
    'centrality_gap': {'step': 5},
    'h2_gap': {'step': 5},
    # Height 0
    'sh0_mult': {'step': 0}, 'sh0_power': {'step': 0.05},
    'nh0_mult': {'step': 5}, 'nh0_power': {'step': 0.05},
    'nn0_mult': {'step': 5}, 'nn0_power': {'step': 0.05},
    # Height 1
    'sh1_mult': {'step': 5}, 'sh1_power': {'step': 0.05},
    'nh1_mult': {'step': 5}, 'nh1_power': {'step': 0.05},
    'ph1_mult': {'step': 5}, 'ph1_power': {'step': 0.05},
    'nn1_mult': {'step': 5}, 'nn1_power': {'step': 0.05},
    # Height 2
    'sh2_mult': {'step': 5}, 'sh2_power': {'step': 0.05},
    'nh2_mult': {'step': 5}, 'nh2_power': {'step': 0.05},
    'ph2_mult': {'step': 5}, 'ph2_power': {'step': 0.05},
}

# Dynamically add god parameters to the search configuration
for god in GOD_LIST:
    param_name = f'god_{god}_bonus'
    PARAM_SEARCH_CONFIG[param_name] = {'step': 10}


# --- Helper Functions ---

def sigmoid(score, k_val):
    """Maps an evaluation score to a win probability (0 to 1) using a given K."""
    return 1 / (1 + np.exp(-k_val * score))


def mse_for_k(k_val, scores, results):
    """Calculates MSE for a given K value."""
    predicted_probs = sigmoid(scores, k_val)
    return np.mean((predicted_probs - results) ** 2)


def objective_function(params_obj, positions, gods_g, gods_b, results):
    """
    Calculates the Mean Squared Error for a given set of parameters.
    This is the function we want to minimize.
    """
    scores = pool.starmap(evaluate_single_position, zip(positions, gods_g, gods_b, repeat(params_obj)))
    predicted_probs = sigmoid(np.array(scores), K)  # Use the global tuned K
    mse = np.mean((predicted_probs - results) ** 2)
    return mse


def evaluate_single_position(pos_text, god_g, god_b, params_obj):
    """Worker function to evaluate a single board position."""
    board = Board(pos_text)
    return score_position(board, params=params_obj, god_g=god_g, god_b=god_b)


def pretty_print_params(params_dict):
    """Prints the parameter dictionary in a readable format."""
    print("  Optimized Parameters:")
    god_params = {k: v for k, v in params_dict.items() if k.startswith('god_')}
    other_params = {k: v for k, v in params_dict.items() if not k.startswith('god_')}

    for key, value in sorted(other_params.items()):
        print(f"    {key}: {value:.4f}" if isinstance(value, float) else f"    {key}: {value}")

    print("\n    --- God Bonuses ---")
    for key, value in sorted(god_params.items()):
        print(f"    {key}: {value}")


# --- Main Execution ---
if __name__ == '__main__':
    # 1. Load the training data
    print("Loading training data...")
    try:
        df = pd.read_csv('training_data.csv')
    except FileNotFoundError:
        print("Error: 'training_data.csv' not found. Please generate it first.")
        exit()

    positions = df['position'].tolist()
    gods_g = df['god_g'].tolist()
    gods_b = df['god_b'].tolist()
    results = df['result'].to_numpy()
    print(f"Loaded {len(positions)} positions.")

    with multiprocessing.Pool() as pool:
        # 2. --- K-Tuning Step ---
        print("\n--- Starting K-Tuning Step ---")
        print("Calculating initial raw scores with fixed parameters...")
        # Calculate scores once using the untuned, C++-equivalent parameters
        raw_scores = np.array(
            pool.starmap(evaluate_single_position, zip(positions, gods_g, gods_b, repeat(FIXED_PARAMS))))

        best_k = K
        best_k_mse = mse_for_k(K, raw_scores, results)
        print(f"Initial K: {K:.6f}, Initial MSE: {best_k_mse:.12f}")

        # Search for a better K in a reasonable range
        for k_candidate in np.arange(0.0005, 0.005, 0.00001):
            current_mse = mse_for_k(k_candidate, raw_scores, results)
            if current_mse < best_k_mse:
                best_k_mse = current_mse
                best_k = k_candidate

        K = best_k  # Update global K with the optimized value
        print(f"Found Optimal K: {K:.6f} (MSE: {best_k_mse:.12f})")

        # 3. --- Main Parameter Optimization ---
        print(f"\n--- Starting Parameter Optimization ({NUM_CYCLES} cycles) ---")
        # Initialize parameters from the fixed values dictionary
        current_params = deepcopy(FIXED_PARAM_VALUES)

        # Calculate the initial error with the starting parameters and new K
        # MODIFIED: Changed Parameters(**current_params) to Parameters(current_params)
        best_mse = objective_function(Parameters(current_params), positions, gods_g, gods_b, results)
        print(f"Initial MSE with new K: {best_mse:.12f}")
        pretty_print_params(current_params)

        # Main optimization loop (Coordinate Ascent)
        for cycle in range(NUM_CYCLES):
            print(f"\n--- Cycle {cycle + 1}/{NUM_CYCLES} ---")
            improved_in_cycle = False

            for param_name, config in PARAM_SEARCH_CONFIG.items():
                # This loop might not find god bonuses if they aren't in FIXED_PARAM_VALUES
                if param_name not in current_params:
                    current_params[param_name] = 0  # Initialize god bonus if not present

                for direction in [-1, 1]:
                    test_params = deepcopy(current_params)
                    step = config['step']
                    test_params[param_name] += direction * step

                    # MODIFIED: Changed Parameters(**test_params) to Parameters(test_params)
                    mse = objective_function(Parameters(test_params), positions, gods_g, gods_b, results)

                    if mse < best_mse:
                        best_mse = mse
                        current_params = test_params
                        improved_in_cycle = True
                        val = current_params[param_name]
                        val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
                        print(f"  Improvement for '{param_name}': {val_str} (MSE: {best_mse:.12f})")

            if not improved_in_cycle:
                print("\nNo improvement in the last cycle. Stopping optimization.")
                break

    # 4. Print final results
    print("\n--- Optimization Finished ---")
    print(f"Final Best Mean Squared Error: {best_mse:.12f}")
    print(f"Using K = {K:.6f}")
    pretty_print_params(current_params)