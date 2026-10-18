"""Fit Total_Risk_Index as a linear function of the sub-scores.

Exploratory analysis for docs/research/facts-to-scores.md. Not production code.

Usage:
    python scripts/fit_total_risk_weights.py [path/to/supplier_risk_dataset.csv]

Needs numpy, pandas, scikit-learn, scipy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score

CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "docs" / "supplier_risk_dataset.csv"

TARGET = "Total_Risk_Index"
OPERATIONAL_NUMERIC = [
    "Purchase Order Volume (EUR)",
    "Order Change Rate",
    "Supplier Delivery Rating",
    "Order Confirmation Rate",
]
OPERATIONAL_CATEGORICAL = ["Sourcing Risk Level", "Supply Chain Complexity"]


def score_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.endswith("_Score") and not c.endswith("_Level")]


def fit(X: pd.DataFrame, y: pd.Series, label: str) -> LinearRegression:
    model = LinearRegression().fit(X, y)
    pred = model.predict(X)
    r2 = model.score(X, y)
    cv = cross_val_score(LinearRegression(), X, y, cv=5, scoring="r2")
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    mae = float(np.mean(np.abs(y - pred)))
    print(f"\n=== {label} ===")
    print(f"n={len(y)}  features={X.shape[1]}  R2={r2:.4f}  5-fold CV R2={cv.mean():.4f}  RMSE={rmse:.3f}  MAE={mae:.3f}")
    print(f"intercept={model.intercept_:.4f}")
    return model


def print_weights(model: LinearRegression, cols: list[str]) -> None:
    coefs = pd.Series(model.coef_, index=cols).sort_values(ascending=False)
    for name, c in coefs.items():
        print(f"  {name:40s} {c:+.4f}")
    print(f"  {'SUM of coefficients':40s} {coefs.sum():+.4f}")


def level_bands(df: pd.DataFrame, cols: list[str]) -> None:
    print("\n=== Level label bands (min-max score per label) ===")
    order = ["Low", "Medium", "High", "Critical"]
    rows = []
    for c in [TARGET] + cols:
        lvl = f"{c}_Level"
        if lvl not in df.columns:
            continue
        g = df.groupby(lvl)[c].agg(["min", "max", "count"])
        row = {"score": c}
        for o in order:
            row[o] = f"{int(g.loc[o, 'min'])}-{int(g.loc[o, 'max'])}" if o in g.index else "-"
        # overlap check: is each label's max below the next label's min?
        present = [o for o in order if o in g.index]
        row["clean_bands"] = all(g.loc[a, "max"] < g.loc[b, "min"] for a, b in zip(present, present[1:]))
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    df = pd.read_csv(CSV)
    cols = score_columns(df)
    y = df[TARGET]
    print(f"Loaded {len(df)} rows from {CSV}")
    print(f"Sub-score columns ({len(cols)}): {cols}")
    print("Missing values per used column:", int(df[cols + [TARGET]].isna().sum().sum()))

    # 1. All sub-scores
    m_all = fit(df[cols], y, "OLS on all sub-scores")
    print_weights(m_all, cols)

    # 2. Constrained-style check: no intercept
    m0 = LinearRegression(fit_intercept=False).fit(df[cols], y)
    print(f"\nNo-intercept fit: R2={m0.score(df[cols], y):.4f}  sum of coefs={m0.coef_.sum():.4f}")

    # 3. Simple equal-weight average
    eq = df[cols].mean(axis=1)
    ss_res = ((y - eq) ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    print(f"Equal-weight mean of all sub-scores: R2={1 - ss_res / ss_tot:.4f}  corr={np.corrcoef(eq, y)[0, 1]:.4f}")

    # 4. Standardised importance
    z = (df[cols] - df[cols].mean()) / df[cols].std()
    mz = LinearRegression().fit(z, y)
    print("\nStandardised coefficients (effect of +1 SD):")
    for name, c in pd.Series(mz.coef_, index=cols).sort_values(ascending=False).items():
        print(f"  {name:40s} {c:+.3f}")

    # 5. Rounding check: does a rounded weighted sum reproduce the integer target exactly?
    pred = m_all.predict(df[cols])
    print(f"\nRounded predictions equal to target: {(np.round(pred) == y).mean():.3%}")
    print(f"Residuals: min={(y - pred).min():.2f}  max={(y - pred).max():.2f}")

    # 6. Do non-score columns add anything?
    extra = pd.get_dummies(df[OPERATIONAL_CATEGORICAL], drop_first=True, dtype=float)
    X_plus = pd.concat([df[cols], df[OPERATIONAL_NUMERIC], extra], axis=1)
    m_plus = fit(X_plus, y, "OLS on sub-scores + operational columns")
    for name, c in pd.Series(m_plus.coef_, index=X_plus.columns).items():
        if name not in cols:
            print(f"  {name:40s} {c:+.6f}")

    # Operational columns alone
    X_ops = pd.concat([df[OPERATIONAL_NUMERIC], extra], axis=1)
    fit(X_ops, y, "OLS on operational columns only")

    # 7. Correlation of sub-scores with target
    print("\nCorrelation of each sub-score with Total_Risk_Index:")
    print(df[cols].corrwith(y).sort_values(ascending=False).round(3).to_string())

    level_bands(df, cols)

    print("\nTotal_Risk_Index distribution:")
    print(y.describe().round(2).to_string())



# Round weights suggested by the OLS fit (they sum to exactly 1.00).
ROUND_WEIGHTS = {
    "Financial_Health_Score": 0.10, "Quality_Risk_Score": 0.10, "Operational_Resilience_Score": 0.10,
    "Compliance_Risk_Score": 0.08,
    "Credit_Rating_Score": 0.06, "Safety_Incident_Score": 0.06, "Sub_Tier_Visibility_Score": 0.06,
    "Geopolitical_Risk_Score": 0.05, "Governance_Risk_Score": 0.05, "ESG_Performance_Score": 0.05,
    "Environmental_Exposure_Score": 0.04, "Labor_Stability_Score": 0.04, "Digital_Security_Score": 0.04,
    "Political_Stability_Score": 0.04, "Industry_Benchmark_Score": 0.04,
    "Market_Sentiment_Score": 0.03, "Media_Sentiment_Score": 0.03, "External_Intelligence_Score": 0.03,
}


def check_round_weights(df: pd.DataFrame) -> None:
    """Integer arithmetic (weights in hundredths) avoids float error at exact .5 ties."""
    w = pd.Series({k: round(v * 100) for k, v in ROUND_WEIGHTS.items()})
    hundredths = df[w.index].mul(w).sum(axis=1)
    y = df[TARGET]
    print(f"\n=== Round weights (sum={w.sum() / 100:.2f}) ===")
    half_even = np.round(hundredths / 100)  # numpy rounds .5 to even, like Python round()
    half_up = (hundredths + 50) // 100
    print(f"  round half to even  exact match {(half_even == y).mean():.3%}")
    print(f"  round half up       exact match {(half_up == y).mean():.3%}")
    print(f"  floor               exact match {((hundredths // 100) == y).mean():.3%}")
    print(f"  max |weighted sum - target| = {(hundredths / 100 - y).abs().max():.3f}")


def check_structure(df: pd.DataFrame, cols: list[str]) -> None:
    c = df[cols].corr()
    print("\n=== Sub-score correlation structure ===")
    country = ["Geopolitical_Risk_Score", "Political_Stability_Score", "Environmental_Exposure_Score"]
    other = [x for x in cols if x not in country]
    print(f"  mean corr within country trio:        {c.loc[country, country].values[np.triu_indices(3, 1)].mean():.3f}")
    oc = c.loc[other, other].values
    print(f"  mean corr among the other 15:         {oc[np.triu_indices(len(other), 1)].mean():.3f}")
    print(f"  mean corr country trio vs other 15:   {c.loc[country, other].values.mean():.3f}")


UMBRELLAS = {
    "Operations & Delivery": ["Operational_Resilience_Score", "Quality_Risk_Score",
                              "Sub_Tier_Visibility_Score", "Digital_Security_Score"],
    "Financial": ["Financial_Health_Score", "Credit_Rating_Score"],
    "People & Safety": ["Labor_Stability_Score", "Safety_Incident_Score", "ESG_Performance_Score"],
    "Legal & Governance": ["Compliance_Risk_Score", "Governance_Risk_Score"],
    "Country & Location": ["Geopolitical_Risk_Score", "Political_Stability_Score",
                           "Environmental_Exposure_Score"],
    "Reputation & Outside View": ["Media_Sentiment_Score", "Market_Sentiment_Score",
                                  "External_Intelligence_Score", "Industry_Benchmark_Score"],
}


def check_umbrellas(df: pd.DataFrame, cols: list[str]) -> None:
    from scipy.cluster.hierarchy import fcluster, linkage

    corr = df[cols].corr()
    group = {s: u for u, members in UMBRELLAS.items() for s in members}
    within, between = [], []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            (within if group[a] == group[b] else between).append(corr.loc[a, b])
    print("\n=== Umbrellas ===")
    print(f"  mean pairwise corr within umbrellas {np.mean(within):.3f}, between {np.mean(between):.3f}")
    for u, members in UMBRELLAS.items():
        sub = corr.loc[members, members].values[np.triu_indices(len(members), 1)]
        weight = sum(ROUND_WEIGHTS[m] for m in members)
        print(f"  {u:28s} weight {weight:.2f}  within-corr {sub.mean():.3f}")
    dist = 1 - corr.values[np.triu_indices(len(cols), 1)]
    labels = fcluster(linkage(dist, "average"), 6, "maxclust")
    print("  Unsupervised average-linkage clustering into 6 groups:")
    for k in sorted(set(labels)):
        print("   ", [cols[j].replace("_Score", "") for j in range(len(cols)) if labels[j] == k])
    ops = df[OPERATIONAL_NUMERIC + [TARGET, "Quality_Risk_Score", "Operational_Resilience_Score"]].corr()
    print("  Correlation of operational metrics with risk scores:")
    print(ops.loc[OPERATIONAL_NUMERIC, [TARGET, "Quality_Risk_Score", "Operational_Resilience_Score"]].round(3).to_string())


def run_all() -> None:
    main()
    df = pd.read_csv(CSV)
    cols = score_columns(df)
    check_round_weights(df)
    check_structure(df, cols)
    check_umbrellas(df, cols)


if __name__ == "__main__":
    run_all()
