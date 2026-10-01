from prometheus_client import REGISTRY

from irmy_common import Config
from irmy_common.metrics import register_build_info, set_up


def _build_info_samples():
    return [
        s for m in REGISTRY.collect() if m.name == "irmy_build_info" for s in m.samples
        if s.name == "irmy_build_info"
    ]


def test_build_info(config_env):
    register_build_info(Config(), service_name="alert_listener")
    samples = _build_info_samples()
    assert len(samples) == 1
    assert samples[0].value == 1
    assert samples[0].labels == {
        "service": "alert_listener", "version": "1.2.3", "platform_version": "2026.9.1", "chart_version": "",
    }


def test_build_info_is_idempotent_and_keeps_one_series(config_env, monkeypatch):
    register_build_info(Config(), service_name="svc")
    monkeypatch.setenv("CHART_VERSION", "0.3.0")
    register_build_info(Config(), service_name="svc")
    samples = _build_info_samples()
    assert len(samples) == 1
    assert samples[0].labels["chart_version"] == "0.3.0"


def test_up():
    set_up(True)
    assert REGISTRY.get_sample_value("irmy_up") == 1
    set_up(False)
    assert REGISTRY.get_sample_value("irmy_up") == 0
