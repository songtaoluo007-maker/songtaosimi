from backend.middleware.rate_limit import _should_rate_limit_path


def test_rate_limit_only_applies_to_non_whitelisted_api_paths():
    assert _should_rate_limit_path("/api/holdings") is True
    assert _should_rate_limit_path("/api/health") is False
    assert _should_rate_limit_path("/") is False
    assert _should_rate_limit_path("/assets/index.js") is False
    assert _should_rate_limit_path("/brand-assets/fund-ai-64.png") is False
