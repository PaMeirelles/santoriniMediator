from itertools import chain
from analysis.visualization import load_data, process_data, merge_sides


def bayesian_wr_symmetric(wins, matches, alpha=2.0):
    wr = {}
    new_wins, new_matches = merge_sides(wins, matches)

    for (a, b), n in new_matches.items():
        w = new_wins[(a, b)]
        wr[(a, b)] = (w + alpha) / (n + 2 * alpha)
    return wr



def conservative_wr():
    data = load_data("Fitos_4.6_Atium")
    matches, wins = process_data(data)
    smoothed_wr = bayesian_wr_symmetric(wins, matches, alpha=2.0)
    return smoothed_wr

print(conservative_wr())