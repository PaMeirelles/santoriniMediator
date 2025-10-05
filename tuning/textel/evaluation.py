# evaluation.py
import math
from game.board import Board
from game.constants import NEIGHBOURS

# --- Constants and Lookups ---

POS_GAPS = [
    0, 1, 2, 1, 0,
    1, 2, 3, 2, 1,
    2, 3, 4, 3, 2,
    1, 2, 3, 2, 1,
    0, 1, 2, 1, 0
]

# Match TEMPO constant from C++
TEMPO = 50

# List of Gods (should match tune.py)
GOD_LIST = [
    'APOLLO', 'ARTEMIS', 'ATHENA', 'ATLAS', 'DEMETER',
    'HEPHAESTUS', 'MINOTAUR', 'PAN', 'PROMETHEUS', 'HERMES'
]

# --- Fixed Parameter Values ---
# This dictionary holds the values for a fixed evaluation configuration.
FIXED_PARAM_VALUES = {
    'centrality_gap': 50,
    'h2_gap': 375,
    # h=0
    'sh0_mult': 30,
    'sh0_power': -0.2,
    'nh0_mult': 45,
    'nh0_power': 0.8,
    'nn0_mult': 55,
    'nn0_power': 1.15,
    # h=1
    'sh1_mult': 50,
    'sh1_power': 0.3,
    'nh1_mult': 180,
    'nh1_power': 0.75,
    'ph1_mult': 55,
    'ph1_power': -0.35,
    'nn1_mult': 55,
    'nn1_power': 0.05,
    # h=2
    'sh2_mult': 210,
    'sh2_power': 0.55,
    'nh2_mult': 445,
    'nh2_power': 1.15,
    'ph2_mult': -15,
    'ph2_power': 0.95,
    # God Bonuses
    'god_APOLLO_bonus': 720,
    'god_ARTEMIS_bonus': -170,
    'god_ATHENA_bonus': 50,
    'god_ATLAS_bonus': -420,
    'god_DEMETER_bonus': -430,
    'god_HEPHAESTUS_bonus': -140,
    'god_HERMES_bonus': -550,
    'god_MINOTAUR_bonus': -80,
    'god_PAN_bonus': -620,
    'god_PROMETHEUS_bonus': 170
}


# --- Helper Function (Unchanged) ---
def power_score(count: int, multiplier: float, power: float) -> float:
    """Calculates score based on the model: y = multiplier * count^power."""
    if count == 0 or multiplier == 0.0:
        return 0.0
    return multiplier * math.pow(count, power)


# --- Parameters Class (Aligned with C++) ---
class Parameters:
    """
    Stores all tunable evaluation parameters, initialized from a dictionary.
    """
    def __init__(self, param_values: dict):
        # --- Base Score Parameters ---
        centrality_gap = param_values['centrality_gap']
        h2_gap = param_values['h2_gap']
        self.posScore = [centrality_gap * gap for gap in POS_GAPS]
        self.heightScore = [0, 100, h2_gap + 100, h2_gap + 50]

        # --- Height-specific parameters ---
        # h=0
        self.sh0_mult = param_values['sh0_mult']
        self.sh0_power = param_values['sh0_power']
        self.nh0_mult = param_values['nh0_mult']
        self.nh0_power = param_values['nh0_power']
        self.nn0_mult = param_values['nn0_mult']
        self.nn0_power = param_values['nn0_power']
        # h=1
        self.sh1_mult = param_values['sh1_mult']
        self.sh1_power = param_values['sh1_power']
        self.nh1_mult = param_values['nh1_mult']
        self.nh1_power = param_values['nh1_power']
        self.ph1_mult = param_values['ph1_mult']
        self.ph1_power = param_values['ph1_power']
        self.nn1_mult = param_values['nn1_mult']
        self.nn1_power = param_values['nn1_power']
        # h=2
        self.sh2_mult = param_values['sh2_mult']
        self.sh2_power = param_values['sh2_power']
        self.nh2_mult = param_values['nh2_mult']
        self.nh2_power = param_values['nh2_power']
        self.ph2_mult = param_values['ph2_mult']
        self.ph2_power = param_values['ph2_power']

        # --- God Bonus Parameters (Control Variables) ---
        self.god_bonuses = {}
        for key, value in param_values.items():
            if key.startswith('god_'):
                # Extracts 'APOLLO' from 'god_APOLLO_bonus'
                god_name = key.split('_')[1].upper()
                self.god_bonuses[god_name] = value

# Instantiate the default parameters using the fixed dictionary
FIXED_PARAMS = Parameters(FIXED_PARAM_VALUES)


# --- Main Evaluation Function (Mirrors C++ Logic) ---
def score_position(b: Board, params: Parameters, god_g: str, god_b: str) -> int:
    """
    Calculates the total score for a given board position from Player 1's perspective.
    """

    def score_worker(worker_idx: int) -> int:
        square = b.workers[worker_idx]
        height = b.blocks[square]

        p_score = params.posScore[square]
        h_score = params.heightScore[height]

        same_h, next_h, next_next_h, prev_h = 0, 0, 0, 0

        for n in NEIGHBOURS[square]:
            if b.is_free(n):
                h = b.blocks[n]
                if h == height:
                    same_h += 1
                elif h == height + 1:
                    next_h += 1
                elif h == height - 1:
                    prev_h += 1
                elif h == height + 2:
                    next_next_h += 1

        support = 0.0
        if height == 0:
            support += power_score(same_h, params.sh0_mult, params.sh0_power)
            support += power_score(next_h, params.nh0_mult, params.nh0_power)
            support += power_score(next_next_h, params.nn0_mult, params.nn0_power)
        elif height == 1:
            support += power_score(same_h, params.sh1_mult, params.sh1_power)
            support += power_score(next_h, params.nh1_mult, params.nh1_power)
            support += power_score(prev_h, params.ph1_mult, params.ph1_power)
            support += power_score(next_next_h, params.nn1_mult, params.nn1_power)
        elif height == 2:
            support += power_score(same_h, params.sh2_mult, params.sh2_power)
            support += power_score(next_h, params.nh2_mult, params.nh2_power)
            support += power_score(prev_h, params.ph2_mult, params.ph2_power)

        return p_score + h_score + int(support)

    # 1. Score for Player 1 (workers 0, 1) and Player 2 (workers 2, 3)
    p1_score = score_worker(0) + score_worker(1)
    p2_score = score_worker(2) + score_worker(3)

    # 2. Base score is the difference
    score = p1_score - p2_score

    # 3. Add tempo bonus if it is Player 1's turn (matches C++ logic)
    # Assumes Board object has a 'turn' attribute where 1 is Player 1.
    if b.turn == 1:
        score += TEMPO

    # 4. Add/Subtract god-specific bonuses as control variables
    score += params.god_bonuses.get(god_g.upper(), 0)
    score -= params.god_bonuses.get(god_b.upper(), 0)

    return score