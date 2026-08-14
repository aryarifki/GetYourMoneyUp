"""Modeling — regression + simple ML helpers for smart-money analysis.

The key distinction in this module is:

1. Association models on historical returns (`back_return_*`)
2. Predictive models on realized forward returns (`fwd_return_*`)

Two angles, deliberately kept simple/interpretable rather than chasing
accuracy with a black box:

1. linear_regression()
   OLS: return ~ bandar_signal_score + foreign_net_flow_pct + volume_ratio
   -> gives you a coefficient + p-value per signal: is it statistically
      distinguishable from zero, given everything else in the model?

2. classify_up_down()
   Simple logistic regression / random forest classifying an up/down return
   target from today's smart-money signals.
   -> gives you accuracy / precision / recall / a feature-importance view,
      i.e. "when the signal is strong, how often does the target return end up
      positive in the training sample?"

Both functions return plain dicts/DataFrames so they're easy to print or
feed into the Streamlit dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_FEATURE_COLS = ["bandar_signal_score", "foreign_net_flow_pct", "volume_ratio"]
_MIN_CLASSIFICATION_ROWS = 8


def _require_statsmodels():
    try:
        import statsmodels.api as sm
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "statsmodels is required for `linear_regression()`. "
            "Install it with `pip install statsmodels` or `pip install -r requirements.txt`."
        ) from exc
    return sm


def _require_sklearn():
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "scikit-learn is required for `classify_up_down()`. "
            "Install it with `pip install scikit-learn` or `pip install -r requirements.txt`."
        ) from exc
    return {
        "RandomForestClassifier": RandomForestClassifier,
        "LogisticRegression": LogisticRegression,
        "accuracy_score": accuracy_score,
        "precision_score": precision_score,
        "recall_score": recall_score,
        "roc_auc_score": roc_auc_score,
        "train_test_split": train_test_split,
        "StandardScaler": StandardScaler,
    }


@dataclass
class RegressionResult:
    target: str
    n_obs: int
    r_squared: float
    coefficients: pd.DataFrame   # columns: feature, coef, std_err, p_value, significant
    summary_text: str


def linear_regression(feat: pd.DataFrame, target_col: str = "back_return_5d",
                       feature_cols: list[str] | None = None) -> RegressionResult:
    """OLS regression of return on smart-money signals.

    Interpretation cheat sheet:
      * coef > 0 and p_value < 0.05 -> signal is associated with *higher*
        target returns, and it's unlikely to be due to chance alone.
      * coef ~ 0 or p_value > 0.05 -> no statistically reliable relationship
        found in this sample — the hypothesis isn't supported (yet / here).
      * r_squared close to 0 -> smart-money signals explain very little of
        day-to-day return variance, which is *normal* for stock returns —
        even a small but significant coefficient can still be meaningful.
    """
    cols = feature_cols or _FEATURE_COLS
    cols = [c for c in cols if c in feat.columns]
    data = feat[cols + [target_col]].apply(pd.to_numeric, errors="coerce").dropna()

    if len(data) < 10 or not cols:
        return RegressionResult(
            target=target_col, n_obs=len(data), r_squared=float("nan"),
            coefficients=pd.DataFrame(), summary_text="Not enough data to fit a model "
            "(need at least 10 complete rows — run the pipeline for more days first).",
        )

    sm = _require_statsmodels()
    X = sm.add_constant(data[cols])
    y = data[target_col]
    # Use Newey-West HAC standard errors for time series robustness
    model = sm.OLS(y, X).fit(cov_type='HAC', cov_kwds={'maxlags': 1})

    coef_df = pd.DataFrame({
        "feature": X.columns,
        "coef": model.params.values,
        "std_err": model.bse.values,
        "p_value": model.pvalues.values,
    })
    coef_df["significant"] = coef_df["p_value"] < 0.05
    coef_df = coef_df[coef_df["feature"] != "const"].reset_index(drop=True)

    return RegressionResult(
        target=target_col, n_obs=int(model.nobs), r_squared=float(model.rsquared),
        coefficients=coef_df, summary_text=str(model.summary()),
    )


@dataclass
class ClassificationResult:
    target: str
    n_obs: int
    accuracy: float
    precision: float
    recall: float
    roc_auc: float | None
    feature_importance: pd.DataFrame
    model_name: str


@dataclass
class ForecastResult:
    target: str
    n_train: int
    predictions: pd.DataFrame
    note: str


def classify_up_down(feat: pd.DataFrame, target_col: str = "back_return_5d",
                      feature_cols: list[str] | None = None,
                      model_type: str = "logistic",
                      test_size: float = 0.25,
                      random_state: int = 42) -> ClassificationResult:
    """Binary classification: will price be up (1) or not (0) over the
    next N days, given today's smart-money signals?

    model_type: "logistic" (simple, interpretable coefficients) or
    "random_forest" (handles non-linearity, gives feature_importances_).

    Note: with a small watchlist + short history this is a *starting point*
    for the hypothesis test, not a production trading signal — check n_obs
    in the result before trusting the metrics.
    """
    cols = feature_cols or _FEATURE_COLS
    cols = [c for c in cols if c in feat.columns]
    data = feat[cols + [target_col]].apply(pd.to_numeric, errors="coerce").dropna()
    data["label"] = (data[target_col] > 0).astype(int)

    if len(data) < _MIN_CLASSIFICATION_ROWS or not cols or data["label"].nunique() < 2:
        return ClassificationResult(
            target=target_col, n_obs=len(data), accuracy=float("nan"),
            precision=float("nan"), recall=float("nan"), roc_auc=None,
            feature_importance=pd.DataFrame(), model_name=model_type,
        )

    sklearn = _require_sklearn()
    X = data[cols]
    y = data["label"]
    X_train, X_test, y_train, y_test = sklearn["train_test_split"](
        X, y, test_size=test_size, random_state=random_state, stratify=y if y.nunique() > 1 else None,
    )

    scaler = sklearn["StandardScaler"]()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    if model_type == "random_forest":
        model = sklearn["RandomForestClassifier"](n_estimators=200, max_depth=4, random_state=random_state)
        model.fit(X_train, y_train)  # tree models don't need scaling
        preds = model.predict(X_test)
        proba = model.predict_proba(X_test)[:, 1]
        importances = pd.DataFrame({"feature": cols, "importance": model.feature_importances_})
        importances = importances.sort_values("importance", ascending=False).reset_index(drop=True)
    else:
        model = sklearn["LogisticRegression"](max_iter=1000)
        model.fit(X_train_s, y_train)
        preds = model.predict(X_test_s)
        proba = model.predict_proba(X_test_s)[:, 1]
        importances = pd.DataFrame({"feature": cols, "importance": model.coef_[0]})
        importances = importances.reindex(
            importances["importance"].abs().sort_values(ascending=False).index
        ).reset_index(drop=True)

    try:
        auc = sklearn["roc_auc_score"](y_test, proba) if y_test.nunique() > 1 else None
    except ValueError:
        auc = None

    return ClassificationResult(
        target=target_col, n_obs=len(data),
        accuracy=sklearn["accuracy_score"](y_test, preds),
        precision=sklearn["precision_score"](y_test, preds, zero_division=0),
        recall=sklearn["recall_score"](y_test, preds, zero_division=0),
        roc_auc=auc,
        feature_importance=importances,
        model_name=model_type,
    )


def forecast_latest(
    feat: pd.DataFrame,
    horizon: int = 5,
    feature_cols: list[str] | None = None,
) -> ForecastResult:
    """Predict future returns for the latest row of each ticker.

    This requires historical broker snapshots with realized forward returns,
    because the training target is `fwd_return_{horizon}d`.
    """
    target_col = f"fwd_return_{horizon}d"
    cols = feature_cols or _FEATURE_COLS
    cols = [c for c in cols if c in feat.columns]
    if target_col not in feat.columns or not cols:
        return ForecastResult(target=target_col, n_train=0, predictions=pd.DataFrame(), note="Required columns are missing.")

    train = feat[cols + [target_col]].apply(pd.to_numeric, errors="coerce").dropna()
    latest = feat.sort_values("date").groupby("ticker").tail(1).copy()
    latest = latest.dropna(subset=cols + ["close"])
    if len(train) < _MIN_CLASSIFICATION_ROWS or latest.empty:
        return ForecastResult(
            target=target_col,
            n_train=len(train),
            predictions=pd.DataFrame(),
            note=(
                "Not enough forward-return training history yet. "
                "Run the pipeline on more trading days so earlier broker snapshots have realized forward returns."
            ),
        )

    sm = _require_statsmodels()
    sklearn = _require_sklearn()

    X_train = train[cols]
    y_train = train[target_col]
    X_latest = latest[cols]

    ols = sm.OLS(y_train, sm.add_constant(X_train, has_constant="add")).fit(cov_type='HAC', cov_kwds={'maxlags': 1})
    latest["ols_expected_return"] = ols.predict(sm.add_constant(X_latest, has_constant="add"))
    latest["ols_predicted_close"] = latest["close"] * (1.0 + latest["ols_expected_return"])

    label_train = (y_train > 0).astype(int)
    if label_train.nunique() >= 2:
        scaler = sklearn["StandardScaler"]()
        X_train_s = scaler.fit_transform(X_train)
        X_latest_s = scaler.transform(X_latest)

        logit = sklearn["LogisticRegression"](max_iter=1000)
        logit.fit(X_train_s, label_train)
        latest["logistic_up_probability"] = logit.predict_proba(X_latest_s)[:, 1]

        rf = sklearn["RandomForestClassifier"](n_estimators=200, max_depth=4, random_state=42)
        rf.fit(X_train, label_train)
        latest["rf_up_probability"] = rf.predict_proba(X_latest)[:, 1]
    else:
        latest["logistic_up_probability"] = np.nan
        latest["rf_up_probability"] = np.nan

    out_cols = [
        "ticker", "date", "close", "bandar_signal", "bandar_signal_score",
        "foreign_net_flow_pct", "volume_ratio",
        "ols_expected_return", "ols_predicted_close",
        "logistic_up_probability", "rf_up_probability",
    ]
    out_cols = [c for c in out_cols if c in latest.columns]
    return ForecastResult(
        target=target_col,
        n_train=len(train),
        predictions=latest[out_cols].sort_values("ols_expected_return", ascending=False).reset_index(drop=True),
        note="Forecasts are exploratory and trained on realized forward returns from prior broker snapshots.",
    )


def hypothesis_verdict(reg: RegressionResult, clf: ClassificationResult) -> str:
    """Plain-language readout combining both models — meant to go straight
    into a notebook markdown cell or the dashboard."""
    lines = []
    if reg.coefficients.empty:
        lines.append("Not enough data to test the hypothesis yet. Run the pipeline for more trading days.")
        return "\n".join(lines)

    sig_rows = reg.coefficients[reg.coefficients["significant"]]
    if sig_rows.empty:
        lines.append(
            f"OLS regression (n={reg.n_obs}, R²={reg.r_squared:.3f}) does not find a statistically "
            f"significant relationship (p<0.05) between the smart money signals and {reg.target}. "
            "The hypothesis is not supported by this sample."
        )
    else:
        bits = [f"{r.feature} (coef={r.coef:+.4f}, p={r.p_value:.3f})" for r in sig_rows.itertuples()]
        lines.append(
            f"OLS regression (n={reg.n_obs}, R²={reg.r_squared:.3f}) finds significant relationships: "
            + "; ".join(bits) + f" for {reg.target}."
        )

    if not np.isnan(clf.accuracy):
        lines.append(
            f"Classification model ({clf.model_name}, n={clf.n_obs}): accuracy {clf.accuracy:.1%}, "
            f"precision {clf.precision:.1%}, recall {clf.recall:.1%}"
            + (f", ROC-AUC {clf.roc_auc:.2f}" if clf.roc_auc else "")
            + ". (A random baseline is about 50% for a balanced two-class problem, so compare the model against that.)"
        )
    else:
        lines.append(
            f"Not enough data for classification yet. At least {_MIN_CLASSIFICATION_ROWS} complete rows are required, "
            f"and more history is strongly recommended."
        )

    return "\n".join(lines)
