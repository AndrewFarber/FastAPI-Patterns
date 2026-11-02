from app.core.config.features import FeatureSettings
from app.core.config.settings import get_settings


def test_static_flags_default_off():
    features = FeatureSettings()
    assert not features.new_checkout and not features.bulk_export


def test_flags_from_env(test_env, monkeypatch):
    monkeypatch.setenv("FEATURES__NEW_CHECKOUT", "true")
    get_settings.cache_clear()
    assert get_settings().features.new_checkout is True
