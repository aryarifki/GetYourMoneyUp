import pytest
import pandas as pd
import math
import sys
import os

from dashboard.app import fmt_rp

def test_fmt_rp_null_values():
    assert fmt_rp(None) == "-"
    assert fmt_rp(pd.NA) == "-"
    assert fmt_rp(float('nan')) == "-"
    assert fmt_rp(math.nan) == "-"

def test_fmt_rp_thousands():
    assert fmt_rp(0) == "Rp 0"
    assert fmt_rp(999) == "Rp 999"
    assert fmt_rp(1000) == "Rp 1,000"
    assert fmt_rp(999999) == "Rp 999,999"

def test_fmt_rp_millions():
    assert fmt_rp(1_000_000) == "Rp 1.00 M"
    assert fmt_rp(1_500_000) == "Rp 1.50 M"
    assert fmt_rp(999_900_000) == "Rp 999.90 M"

def test_fmt_rp_billions():
    assert fmt_rp(1_000_000_000) == "Rp 1.00 B"
    assert fmt_rp(1_500_000_000) == "Rp 1.50 B"
    assert fmt_rp(999_900_000_000) == "Rp 999.90 B"

def test_fmt_rp_trillions():
    assert fmt_rp(1_000_000_000_000) == "Rp 1.00 T"
    assert fmt_rp(1_500_000_000_000) == "Rp 1.50 T"

def test_fmt_rp_negative_values():
    assert fmt_rp(-1000) == "-Rp 1,000"
    assert fmt_rp(-1_500_000) == "-Rp 1.50 M"
    assert fmt_rp(-1_500_000_000) == "-Rp 1.50 B"
    assert fmt_rp(-1_500_000_000_000) == "-Rp 1.50 T"

def test_fmt_rp_float_inputs():
    assert fmt_rp(1234.56) == "Rp 1,235"
    assert fmt_rp(1_234_567.89) == "Rp 1.23 M"

def test_fmt_rp_string_inputs():
    assert fmt_rp("1000") == "Rp 1,000"
    assert fmt_rp("-1500000") == "-Rp 1.50 M"
    assert fmt_rp("0") == "Rp 0"
