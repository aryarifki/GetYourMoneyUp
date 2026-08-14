import pytest
import pandas as pd
import numpy as np
from src.idx_bandarmology.modeling import (
    RegressionResult,
    ClassificationResult,
    hypothesis_verdict,
)

def test_hypothesis_verdict_empty_regression():
    reg = RegressionResult(
        target="target",
        n_obs=0,
        r_squared=float("nan"),
        coefficients=pd.DataFrame(),
        summary_text=""
    )
    clf = ClassificationResult(
        target="target",
        n_obs=0,
        accuracy=float("nan"),
        precision=float("nan"),
        recall=float("nan"),
        roc_auc=None,
        feature_importance=pd.DataFrame(),
        model_name="logistic"
    )
    result = hypothesis_verdict(reg, clf)
    assert "Not enough data to test the hypothesis yet" in result


def test_hypothesis_verdict_no_significant_relationships():
    reg_df = pd.DataFrame({
        "feature": ["f1", "f2"],
        "coef": [0.1, 0.2],
        "std_err": [0.1, 0.1],
        "p_value": [0.1, 0.2],
        "significant": [False, False]
    })
    reg = RegressionResult(
        target="back_return_5d",
        n_obs=100,
        r_squared=0.05,
        coefficients=reg_df,
        summary_text="Summary"
    )

    # Still no classification data
    clf = ClassificationResult(
        target="back_return_5d",
        n_obs=100,
        accuracy=float("nan"),
        precision=float("nan"),
        recall=float("nan"),
        roc_auc=None,
        feature_importance=pd.DataFrame(),
        model_name="logistic"
    )
    result = hypothesis_verdict(reg, clf)
    assert "does not find a statistically significant relationship" in result
    assert "OLS regression (n=100, R²=0.050)" in result
    assert "Not enough data for classification yet" in result


def test_hypothesis_verdict_significant_and_classified():
    reg_df = pd.DataFrame({
        "feature": ["f1", "f2"],
        "coef": [0.5, -0.2],
        "std_err": [0.1, 0.1],
        "p_value": [0.01, 0.2],
        "significant": [True, False]
    })
    reg = RegressionResult(
        target="fwd_return_5d",
        n_obs=200,
        r_squared=0.15,
        coefficients=reg_df,
        summary_text="Summary"
    )

    clf = ClassificationResult(
        target="fwd_return_5d",
        n_obs=200,
        accuracy=0.6,
        precision=0.65,
        recall=0.55,
        roc_auc=None, # Testing no ROC-AUC case
        feature_importance=pd.DataFrame(),
        model_name="random_forest"
    )
    result = hypothesis_verdict(reg, clf)
    assert "finds significant relationships: f1 (coef=+0.5000, p=0.010) for fwd_return_5d" in result
    assert "Classification model (random_forest, n=200)" in result
    assert "accuracy 60.0%, precision 65.0%, recall 55.0%" in result
    assert "ROC-AUC" not in result

def test_hypothesis_verdict_with_roc_auc():
    reg_df = pd.DataFrame({
        "feature": ["f1"],
        "coef": [0.5],
        "std_err": [0.1],
        "p_value": [0.01],
        "significant": [True]
    })
    reg = RegressionResult(
        target="fwd_return_5d",
        n_obs=200,
        r_squared=0.15,
        coefficients=reg_df,
        summary_text="Summary"
    )

    clf = ClassificationResult(
        target="fwd_return_5d",
        n_obs=200,
        accuracy=0.6,
        precision=0.65,
        recall=0.55,
        roc_auc=0.72,
        feature_importance=pd.DataFrame(),
        model_name="logistic"
    )
    result = hypothesis_verdict(reg, clf)
    assert "ROC-AUC 0.72" in result
