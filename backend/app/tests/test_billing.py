"""Tests for billing usage limits (§15, §18)."""
from app.billing import usage


def test_plan_limits_defaults():
    assert usage.get_plan_limit("free") == 20
    assert usage.get_plan_limit("starter") == 200
    assert usage.get_plan_limit("pro") == 1000
    assert usage.get_plan_limit("business") >= 1000


def test_plan_limits_unknown_falls_back_to_free():
    assert usage.get_plan_limit("nonexistent") == 20


def test_plan_price_env_mapping():
    assert usage.PLAN_PRICE_ENV["starter"] == "stripe_price_starter_monthly"
    assert usage.PLAN_PRICE_ENV["pro"] == "stripe_price_pro_monthly"
    assert usage.PLAN_PRICE_ENV["business"] == "stripe_price_business_monthly"
