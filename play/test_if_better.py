import pandas as pd, numpy as np, matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from analysis.visualization import load_data
from scipy.stats import binom_test


from statsmodels.stats.proportion import proportion_confint

# Specify engine names; note here we assume new_engine is the “new” engiA gnt ne under test.
base = "Fitos_13.1_Legacy"
new_engine = "Fitos_14.8_Echo"

# Load and prepare data
df = load_data(new_engine, base)
pos_key = "Starting_pos"  # unique board‑position column
# Keep only paired games (where exactly two games were played with the same starting position)
g = df.groupby(pos_key).filter(lambda x: len(x) == 2)
# Label winner: if Result > 0 then Engine_G wins,
# else base wins
g["Winner"] = np.where(g["Result"] > 0, g["Engine_G"], g["Engine_B"])

# ---------- HEATMAP OF GOD MATCHUPS ----------
gods = sorted(set(g["God_A"]).union(g["God_B"]))

heat = pd.DataFrame(np.nan, index=gods, columns=gods)

# Calculate win‑rate difference (A − B) for each God matchup
for (_, d) in g.groupby(["God_A", "God_B"]):
    ga, gb = d.iloc[0][["God_A", "God_B"]]
    wa = (d["Winner"] == new_engine).sum()
    wb = (d["Winner"] == base).sum()
    t = wa + wb
    if t:
        heat.loc[ga, gb] = wa / t - wb / t  # range −1 … +1

# Plot the heatmap
fig, ax = plt.subplots(figsize=(10, 8))
# new_engine layer in light‑gray
ax.imshow(np.ones_like(heat) * 0, cmap=ListedColormap(["lightgray"]), interpolation="none")
im = ax.imshow(heat, cmap="RdBu", vmin=-1, vmax=1, interpolation="none")
ax.set_xticks(range(len(gods)))
ax.set_xticklabels(gods, rotation=90)
ax.set_yticks(range(len(gods)))
ax.set_yticklabels(gods)
for i in range(len(gods)):
    for j in range(len(gods)):

        if i != j and not np.isnan(heat.iat[i, j]):
            ax.text(j, i, f"{100*heat.iat[i, j]:.0f}%", ha="center", va="center", fontsize=8, color="black")
plt.colorbar(im, ax=ax, label="Win‑rate Δ (A − B)")
plt.tight_layout()
plt.show()

# ---------- PER‑GOD WIN‑RATE TABLES ----------
tab = pd.DataFrame(index=gods, columns=[new_engine, base], dtype=float)
games = pd.DataFrame(index=gods, columns=[new_engine, base], dtype=int)
for god in gods:
    for eng in (new_engine, base):
        p_subset = g[((g["God_A"] == god) & (g["Engine_G"] == eng)) |
                     ((g["God_B"] == god) & (g["Engine_B"] == eng))]
        if len(p_subset):
            wins = (((p_subset["Result"] == 1) & (p_subset["Engine_G"] == eng)).sum() +
                    ((p_subset["Result"] == -1) & (p_subset["Engine_B"] == eng)).sum())
            tab.loc[god, eng] = wins / len(p_subset)
            games.loc[god, eng] = len(p_subset)

print("\nWin‑rates (%)")
print((tab * 100).round(1).fillna("—"))
print("\nGames played")
print(games.fillna(0).astype(int))

# ---------- POSITION OUTCOME SUMMARY ----------
# For each starting position (i.e. each pair), label it as:
#   "2‑0" if new_engine wins both,
#   "0‑2" if base wins both,
#   "1‑1" otherwise.
outcome = g.groupby(pos_key).apply(
    lambda d: ((d["Winner"] == new_engine).sum(), (d["Winner"] == base).sum())
).apply(lambda x: "2‑0" if x[0] == 2 else "0‑2" if x[1] == 2 else "1‑1")

# ---------- DECISIVE MATCHES ----------
# Decisive pairs: those that ended as either "2‑0" or "0‑2"
decisive_keys = outcome[outcome.isin(["2‑0", "0‑2"])].index
decisive_df = g[g[pos_key].isin(decisive_keys)][["Id", "God_A", "God_B", "Winner"]].sort_values(["Id"])
pd.set_option('display.max_columns', 10)
print("\nDecisive match IDs")
print(decisive_df)

summary = outcome.value_counts().rename("Count")
print("\nPosition outcomes")
print(summary)

# ---------- STATISTICAL COMPARISON OF DECISIVE OUTCOMES ----------

# Focus only on decisive outcomes.
decisive_outcomes = outcome[outcome.isin(["2‑0", "0‑2"])]
W_decisive = (decisive_outcomes == "2‑0").sum()  # decisive wins for new_engine
L_decisive = (decisive_outcomes == "0‑2").sum()  # decisive wins for base
K = W_decisive + L_decisive  # total decisive paired matches

if K > 0:
    win_rate = W_decisive / K
else:
    win_rate = np.nan

# Compute statistics: one‑sided binomial test against 50% and 95% Wilson confidence interval.
if K > 0:
    p_val = binom_test(W_decisive, K, p=0.5, alternative='greater')
    ci_low, ci_upp = proportion_confint(W_decisive, K, alpha=0.05, method='wilson')
else:
    p_val = np.nan
    ci_low, ci_upp = (np.nan, np.nan)

# Assemble the report into a table (pandas

# DataFrame)
report = pd.DataFrame({
    "Decisive Wins": [W_decisive],

    "Decisive Losses": [L_decisive],
    "Total Decisive Pairs": [K],
    "Win Rate (%)": [win_rate*100 if K > 0 else np.nan],
    "p-value": [p_val],
    "95% CI Lower (%)": [ci_low*100 if K > 0 else np.nan],
    "95% CI Upper (%)": [ci_upp*100 if K > 0 else np.nan]
})
print("\nStatistical Report on Decisive Matches:")
print(report)

# ---------- DECISION RULES ----------

# We want to stop the experiment when either condition is met:
# 1. We are confident (p <= 0.05) that win rate > 50%
# 2. We are confident that win rate is not high enough to meet our practical threshold: the entire 95% CI lies below 52%.
#
# The decision is made "whichever comes first".

if K == 0:
    conclusion = "Inconclusive: Not enough decisive matches to perform a statistical test."
else:
    if p_val <= 0.05:

        # We have strong evideince that win rate > 50%
        conclusion = (f"Conclusion: New engine is significantly better than chance (p={p_val:.4f}); "
                      f"observed win rate = {win_rate*100:.2f}% "
                      f"with 95% CI [{ci_low*100:.2f}%, {ci_upp*100:.2f}%].")
    elif ci_upp < 0.52:
        # We are confident that even the upper bound is below our practical threshold
        conclusion = f"Conclusion: New engine does NOT reach the practical threshold (upper CI = {ci_upp * 100:.2f}% < 52%)."
    else:

        conclusion = "Inconclusive: Neither condition is met; more matches are needed."

print("\n" + conclusion)