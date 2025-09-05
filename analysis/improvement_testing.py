import pymc as pm
import pandas as pd
from analysis.visualization import load_data
from game.board import God


def get_per_game_data(old_engine: str, new_engine: str) -> pd.DataFrame:
    df = load_data(new_engine, old_engine)
    records = []
    for _, row in df.iterrows():
        result = row["Result"]

        for engine_label, is_gray, god_col, opp_col in [
            (row["Engine_G"], True, "God_A", "God_B"),
            (row["Engine_B"], False, "God_B", "God_A")
        ]:
            if result == 1 and is_gray:
                win = 1
            elif result == -1 and not is_gray:
                win = 1
            else:
                win = 0

            record = {
                "Engine": 1 if engine_label == new_engine else 0,  # 1 = New, 0 = Old
                "God": row[god_col],
                "Opponent": row[opp_col],
                "Role": 0 if is_gray else 1,  # 0 = Gray, 1 = Blue
                "Win": win
            }
            records.append(record)

    return pd.DataFrame(records)


def run_full_comparison_model(old_engine: str, new_engine: str, draws=2000, chains=4, seed=42):
    df = get_per_game_data(old_engine, new_engine)
    valid_gods = [g.name for g in God]
    df = df[df["God"].isin(valid_gods) & df["Opponent"].isin(valid_gods)]

    god_idx, gods = pd.factorize(df["God"].values)
    opp_idx, _ = pd.factorize(df["Opponent"].values)
    engine = df["Engine"].values  # 1 = New engine, 0 = Old engine
    win = df["Win"].values

    with pm.Model() as model:
        mu = pm.Normal("mu", mu=0, sigma=1)
        sigma_g = pm.HalfNormal("sigma_g", sigma=1)
        sigma_o = pm.HalfNormal("sigma_o", sigma=1)

        god_effect = pm.Normal("god_effect", mu=0, sigma=sigma_g, shape=len(gods))
        opponent_effect = pm.Normal("opponent_effect", mu=0, sigma=sigma_o, shape=len(gods))
        engine_effect = pm.Normal("engine_effect", mu=0, sigma=1, shape=len(gods))

        logit_p = (
            mu +
            god_effect[god_idx] +
            opponent_effect[opp_idx] +
            engine_effect[god_idx] * engine
        )
        p = pm.Deterministic("p", pm.math.sigmoid(logit_p))

        pm.Bernoulli("win", p=p, observed=win)

        trace = pm.sample(draws=draws, chains=chains, random_seed=seed, target_accept=0.9)

    return trace, gods


def check_engine_improvement(trace, god_names, threshold=0.95):
    engine_effects = trace.posterior["engine_effect"].stack(samples=("chain", "draw"))
    probs = (engine_effects > 0).mean("samples")
    godwise = pd.DataFrame({
        "God": god_names,
        "Prob(Improved)": probs.values
    })
    all_prob = (probs > threshold).all().item()
    summary = "All gods improved" if all_prob else "Some gods regressed"
    return godwise.sort_values("Prob(Improved)"), summary


if __name__ == "__main__":
    trace, gods = run_full_comparison_model("Fitos_8.1_Cursed",  "Fitos_9.4_Moth")
    godwise_df, summary = check_engine_improvement(trace, gods)

    print(summary)
    print(godwise_df.to_string(index=False))