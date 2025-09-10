from itertools import combinations
from analysis.visualization.visualization import load_data, process_data, merge_sides


def bayesian_wr_symmetric(wins, matches, alpha=2.0):
    wr = {}
    new_wins, new_matches = merge_sides(wins, matches)

    for (a, b), n in new_matches.items():
        w = new_wins[(a, b)]
        wr[(a, b)] = (w + alpha) / (n + 2 * alpha)
    return wr

def conservative_wr():
    data = load_data("Fitos_5.1_Truthless")
    matches, wins = process_data(data)
    smoothed_wr = bayesian_wr_symmetric(wins, matches, alpha=2.0)
    return smoothed_wr

# Tier order from weakest to strongest
TIER_ORDER = ['D', 'C', 'B', 'A', 'S']

# Winrate mapping per tier difference
TIER_DIFF_TO_WR = {
    0: 0.5,
    1: 0.55,
    2: 0.6,
    3: 0.65,
    4: 0.7,
    5: 0.75,
    6: 0.8,
    7: 0.85
}

def tier_distance(t1, t2):
    return abs(TIER_ORDER.index(t1) - TIER_ORDER.index(t2))

def compute_wr_matrix(god_tiers, matchup_adjustments=None):
    matchup_adjustments = matchup_adjustments or {}
    wr = {}
    gods = sorted(god_tiers)

    for a, b in combinations(gods, 2):
        t_diff = TIER_ORDER.index(god_tiers[a]) - TIER_ORDER.index(god_tiers[b])
        adj = matchup_adjustments.get((a, b), matchup_adjustments.get((b, a), 0))
        eff_diff = t_diff + adj
        capped = max(-max(TIER_DIFF_TO_WR), min(max(TIER_DIFF_TO_WR), eff_diff))
        val = round(TIER_DIFF_TO_WR.get(abs(capped), 0.5), 2)

        wr[(a, b)] = val if eff_diff >= 0 else 1 - val
        wr[(b, a)] = 1 - wr[(a, b)]

    return wr


god_tiers = {
    "APOLLO": "S",
    "ARTEMIS": "A",
    "ATHENA": "A",
    "ATLAS": "B",
    "DEMETER": "A",
    "HERMES": "C",
    "HEPHAESTUS": "B",
    "MINOTAUR": "B",
    "PAN": "C",
    "PROMETHEUS": "A",
}

matchup_adjustments = {
    ("APOLLO", "ARTEMIS"): -1,
    ("APOLLO", "ATHENA"): -1 ,
    ("ARTEMIS", "ATLAS"): -1,
    ("ARTEMIS", "HEPHAESTUS"): +1,
    ("ARTEMIS", "PAN"): +2,
    ("ATHENA", "PAN"): -2,
    ("ATHENA", "MINOTAUR"): +1,
    ("ATHENA", "DEMETER"): +1,
    ("ATLAS", "DEMETER"): -1,
    ("ATLAS", "MINOTAUR"): +2,
    ("ATLAS", "HERMES"): -2,
    ("DEMETER", "ATLAS"): -1,
    ("DEMETER", "HEPHAESTUS"): -1,
    ("HERMES", "ATHENA"): -1,
    ("HERMES", "PAN"): -1,
    ("HEPHAESTUS", "APOLLO"): +1,
    ("HEPHAESTUS", "MINOTAUR"): +1,
    ("MINOTAUR", "PAN"): +3
}

import itertools


def calc_series_win_probability(game_probs):
    """
    Given a list of 5 independent win probabilities for a player,
    return the probability that the player wins at least 3 of the 5 games.
    """
    n = len(game_probs)
    total_prob = 0.0
    for k in range(3, n + 1):
        for subset in itertools.combinations(range(n), k):
            p = 1.0
            for i in range(n):
                if i in subset:
                    p *= game_probs[i]
                else:
                    p *= (1.0 - game_probs[i])
            total_prob += p
    return total_prob


def generate_all_matchings(gods):
    """
    Generate all ways to partition the list of gods into 5 disjoint pairs
    (perfect matchings).
    """
    if not gods:
        yield []
        return
    first = gods[0]
    for i in range(1, len(gods)):
        pair = gods[i]
        remaining = gods[1:i] + gods[i + 1:]
        for rest in generate_all_matchings(remaining):
            yield [(first, pair)] + rest


def solve_fair_bo5(P1, P2):
    """
    Solve the fairness-optimized Bo5 match selection problem using
    single-dictionary matchup data:

    - P1[(a,b)] = Probability that 'a' beats 'b' (from Player1's perspective).
    - P2[(a,b)] = Probability that 'a' beats 'b' (from Player2's perspective).

    Returns (best_min_value, best_assignment).
    """
    # Gather the full set of gods from both P1 and P2
    all_gods = set()
    for (a, b) in P1.keys():
        all_gods.add(a)
        all_gods.add(b)
    for (a, b) in P2.keys():
        all_gods.add(a)
        all_gods.add(b)
    all_gods = sorted(all_gods)

    best_min_value = -1.0
    best_assignment = None

    # Generate all partitions of the 10 gods into 5 pairs
    for pairing in generate_all_matchings(all_gods):

        # For each pairing, we consider 2^5 side assignments
        # side=0 => P1 uses the first god, P2 uses the second
        # side=1 => P1 uses the second god, P2 uses the first
        for side_assignment in itertools.product([0, 1], repeat=5):
            p1_game_probs = []
            p2_game_probs = []

            for (a, b), side in zip(pairing, side_assignment):
                if side == 0:
                    # P1 = a, P2 = b
                    p1_game_probs.append(P1[(a, b)])
                    p2_game_probs.append(P2[(b, a)])
                else:
                    # P1 = b, P2 = a
                    p1_game_probs.append(P1[(b, a)])
                    p2_game_probs.append(P2[(a, b)])

            p1_series_win = calc_series_win_probability(p1_game_probs)
            p2_series_win = calc_series_win_probability(p2_game_probs)
            fair_value = min(p1_series_win, p2_series_win)

            if fair_value > best_min_value:
                best_min_value = fair_value
                best_assignment = {
                    'pairs': pairing,
                    'sides': side_assignment
                }

    return best_min_value, best_assignment


# ------------------------------------------------------------------------------
# Example usage
if __name__ == "__main__":
    bot_wr = conservative_wr()
    my_wr = compute_wr_matrix(god_tiers, matchup_adjustments)

    best_min_val, best_sol = solve_fair_bo5(bot_wr, my_wr)
    print("Maximized min(P1_series_win, P2_series_win) =", round(best_min_val, 4))
    for i, (pair) in enumerate(best_sol['pairs']):
        side = best_sol['sides'][i]
        if side == 0:
            print(f"Game {i + 1}: P1={pair[0]} vs P2={pair[1]}")
        else:
            print(f"Game {i + 1}: P1={pair[1]} vs P2={pair[0]}")
