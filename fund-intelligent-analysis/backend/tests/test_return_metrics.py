from datetime import date

from backend.services.return_metrics_v3 import calc_max_drawdown, xirr


def test_xirr_handles_regular_investment_cash_flows():
    result = xirr([
        (date(2025, 1, 1), -10_000),
        (date(2025, 7, 1), -10_000),
        (date(2026, 1, 1), 22_000),
    ])

    assert result > 0
    assert 13.3 < result * 100 < 13.5


def test_xirr_returns_zero_when_cash_flows_have_no_sign_change():
    assert xirr([(date(2025, 1, 1), -1000), (date(2025, 2, 1), -500)]) == 0


def test_calc_max_drawdown_tracks_current_and_recovery():
    result = calc_max_drawdown([
        (date(2025, 1, 1), 100),
        (date(2025, 1, 2), 120),
        (date(2025, 1, 3), 90),
        (date(2025, 1, 4), 121),
        (date(2025, 1, 5), 110),
    ])

    assert result["max_dd"] == 25.0
    assert result["peak_date"] == "2025-01-02"
    assert result["trough_date"] == "2025-01-03"
    assert result["recovery_days"] == 1
    assert result["current_dd"] == 9.09
