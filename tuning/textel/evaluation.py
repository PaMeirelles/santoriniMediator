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

# --- ADDED: List of Gods (should match tune.py) ---
GOD_LIST = [
    'APOLLO', 'ARTEMIS', 'ATHENA', 'ATLAS', 'DEMETER',
    'HEPHAESTUS', 'MINOTAUR', 'PAN', 'PROMETHEUS', 'HERMES'
]


# --- Helper Function (Unchanged) ---
def power_score(count: int, multiplier: float, power: float) -> float:
    """Calculates score based on the model: y = multiplier * count^power."""
    if count == 0 or multiplier == 0.0:
        return 0.0
    return multiplier * math.pow(count, power)


# --- MODIFIED: Parameters Class ---
class Parameters:
    """
    Stores all tunable evaluation parameters, including tempo and god bonuses.
    """

    def __init__(self, tempo_bonus=0, **kwargs):
        # --- Base Score Parameters (driven by kwargs) ---
        centrality_gap = kwargs.get('centrality_gap', 50)
        h2_gap = kwargs.get('h2_gap', 415)
        self.posScore = [centrality_gap * gap for gap in POS_GAPS]
        self.heightScore = [0, 100, h2_gap + 100, h2_gap + 50]

        # --- Height-specific parameters (driven by kwargs) ---
        # h=0
        self.sh0_mult = kwargs.get('sh0_mult', 0)
        self.sh0_power = kwargs.get('sh0_power', 0)
        self.nh0_mult = kwargs.get('nh0_mult', 0)
        self.nh0_power = kwargs.get('nh0_power', 0)
        self.nn0_mult = kwargs.get('nn0_mult', 0)
        self.nn0_power = kwargs.get('nn0_power', 0)
        # h=1
        self.sh1_mult = kwargs.get('sh1_mult', 0)
        self.sh1_power = kwargs.get('sh1_power', 0)
        self.nh1_mult = kwargs.get('nh1_mult', 0)
        self.nh1_power = kwargs.get('nh1_power', 0)
        self.ph1_mult = kwargs.get('ph1_mult', 0)
        self.ph1_power = kwargs.get('ph1_power', 0)
        self.nn1_mult = kwargs.get('nn1_mult', 0)
        self.nn1_power = kwargs.get('nn1_power', 0)
        # h=2
        self.sh2_mult = kwargs.get('sh2_mult', 0)
        self.sh2_power = kwargs.get('sh2_power', 0)
        self.nh2_mult = kwargs.get('nh2_mult', 0)
        self.nh2_power = kwargs.get('nh2_power', 0)
        self.ph2_mult = kwargs.get('ph2_mult', 0)
        self.ph2_power = kwargs.get('ph2_power', 0)

        # --- ADDED: Tempo and God Bonus Parameters ---
        self.tempo_bonus = tempo_bonus
        self.god_bonuses = {}
        for key, value in kwargs.items():
            if key.startswith('god_'):
                # Extracts 'Apollo' from 'god_apollo_bonus'
                god_name = key.split('_')[1]
                self.god_bonuses[god_name] = value


fixed_param_values = {
    'centrality_gap': 40,
    'h2_gap': 340,
    'nh0_mult': 60,
    'nh0_power': 0.65,
    'nh1_mult': 175,
    'nh1_power': 0.7,
    'nh2_mult': 410,
    'nh2_power': 1.1,
    'nn0_mult': 60,
    'nn0_power': 1,
    'nn1_mult': 45,
    'nn1_power': 0.4,
    'ph1_mult': 10,
    'ph1_power': 0.4,
    'ph2_mult': -25,
    'ph2_power': 0.25,
    'sh0_mult': -5,
    'sh0_power': 0.15,
    'sh1_mult': 50,
    'sh1_power': 0.28,
    'sh2_mult': 175,
    'sh2_power': 0.55,
    'tempo_bonus': 450,
    'god_apollo_bonus': 600,
    'god_artemis_bonus': -180,
    'god_athena_bonus': 20,
    'god_atlas_bonus': -390,
    'god_demeter_bonus': -410,
    'god_hephaestus_bonus': -150,
    'god_hermes_bonus': -510,
    'god_minotaur_bonus': -100,
    'god_pan_bonus': -570,
    'god_prometheus_bonus': 120
}

# Instantiate the default parameters using the dictionary
FIXED_PARAMS = Parameters(**fixed_param_values)


# --- MODIFIED: Main Evaluation Function ---

def score_position(b: Board, params: Parameters, tempo: str, god_g: str, god_b: str) -> int:
    """
    Calculates the total score for a given board position from Gold's perspective.
    Accepts tempo and god information for more accurate scoring.
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

    # --- Score Calculation ---

    # 1. Individual worker scores (Gold is player 1, Blue is player 2)
    p1_score = score_worker(0) + score_worker(1)
    p2_score = score_worker(2) + score_worker(3)

    # 2. Base score is the difference between player scores
    score = p1_score - p2_score

    # 3. Add tempo bonus based on whose turn it is
    # The score is from Gold's perspective, so add if Gold's turn, subtract if Blue's
    if tempo == 'g':
        score += params.tempo_bonus
    elif tempo == 'b':
        score -= params.tempo_bonus

    # 4. Add/Subtract god-specific bonuses
    # Use .get(god, 0) to handle cases where a god might not be in the tuned list
    score += params.god_bonuses.get(god_g, 0)
    score -= params.god_bonuses.get(god_b, 0)

    return score