#!/usr/bin/env python3
"""
Bradley–Terry Rating Estimator for Gods

This script reads a CSV file with match results between gods, where each row
has the format:
    God_A,God_B,Result
with Result = 1 indicating a win for God_A and -1 for a win for God_B.

It then estimates the "ability" (rating) of each god using the Bradley–Terry
model, which is less sensitive to the order in which matches are processed.
Finally, it prints the gods and their ratings in a nicely formatted table,
with ratings normalized so that the worst god has a rating of 0 and scaled for
readability.
"""

import csv
from collections import defaultdict


def read_matches(filename):
    """
    Reads the CSV file and returns:
      - gods: a set of all god names
      - wins: a nested dictionary wins[i][j] = number of wins of god i over god j
      - matches: a nested dictionary matches[i][j] = total matches between god i and god j
    """
    gods = set()
    wins = defaultdict(lambda: defaultdict(int))
    matches = defaultdict(lambda: defaultdict(int))

    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            god_a = row['God_A']
            god_b = row['God_B']
            result = int(row['Result'])

            gods.add(god_a)
            gods.add(god_b)

            # Record that a match occurred between god_a and god_b.
            matches[god_a][god_b] += 1
            matches[god_b][god_a] += 1

            # Record wins.
            if result == 1:
                wins[god_a][god_b] += 1
            elif result == -1:
                wins[god_b][god_a] += 1
            # (If draws were possible, you could incorporate them here.)

    return gods, wins, matches


def bradley_terry(gods, wins, matches, max_iter=1000, tol=1e-5):
    """
    Estimates the ability rating for each god using an iterative
    Bradley–Terry model.

    Each god i is assigned a rating p_i (initially 1.0). For every iteration,
    each rating is updated according to:

         p_i(new) = (total wins of i) / (sum over opponents j of (n_ij / (p_i + p_j)))

    The iterations stop when the maximum change is below tol.

    Returns:
        dict: A dictionary mapping each god to its estimated rating.
    """
    # Initialize all ratings to 1.0.
    ratings = {g: 1.0 for g in gods}

    for iteration in range(max_iter):
        new_ratings = {}
        max_change = 0.0

        for g in gods:
            total_wins = sum(wins[g].values())  # total wins for god g
            denom = 0.0
            # Sum over every opponent j that played against g.
            for j, n in matches[g].items():
                # Avoid division by zero (should not happen if ratings are positive).
                denom += n / (ratings[g] + ratings[j])
            # If no matches recorded (shouldn't occur here), keep the same rating.
            new_rating = ratings[g] if denom == 0 else total_wins / denom
            new_ratings[g] = new_rating
            max_change = max(max_change, abs(new_rating - ratings[g]))

        ratings = new_ratings
        if max_change < tol:
            break

    return ratings


def print_ratings_table(ratings, scaling_factor=1000):
    """
    Prints the ratings in a pretty table, with ratings normalized so that
    the lowest rating becomes 0, and scaled by a given factor for readability.
    """
    # Normalize ratings: subtract the minimum rating from all.
    min_rating = min(ratings.values())
    normalized = {g: r - min_rating for g, r in ratings.items()}
    # Optionally scale the ratings.
    scaled = {g: normalized[g] * scaling_factor for g in normalized}

    # Order gods by rating descending.
    sorted_ratings = sorted(scaled.items(), key=lambda x: x[1], reverse=True)

    # Determine column widths.
    god_col_width = max(len("God"), max(len(g) for g, _ in sorted_ratings))
    rating_col_width = max(len("Rating"), 8)

    # Build table lines.
    horizontal_line = f"+{'-' * (god_col_width + 2)}+{'-' * (rating_col_width + 2)}+"
    header = f"| {'God'.ljust(god_col_width)} | {'Rating'.ljust(rating_col_width)} |"

    print(horizontal_line)
    print(header)
    print(horizontal_line)
    for god, rating in sorted_ratings:
        print(f"| {god.ljust(god_col_width)} | {rating:>{rating_col_width}.2f} |")
    print(horizontal_line)


def main():
    # Path to the CSV file (adjust as needed).
    filename = "../match_results.csv"
    gods, wins, matches = read_matches(filename)
    ratings = bradley_terry(gods, wins, matches)
    print_ratings_table(ratings)


if __name__ == '__main__':
    main()
