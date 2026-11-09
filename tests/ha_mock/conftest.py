import importlib
import sys

import pytest
from homeassistant import loader

from .harness import HOME, prepare_config_dir


def _point_custom_components_at(cfg: str) -> None:
    """HA finds custom components by importing the `custom_components` package from sys.path."""
    for name in [m for m in sys.modules if m == "custom_components" or m.startswith("custom_components.")]:
        del sys.modules[name]
    if cfg not in sys.path:
        sys.path.insert(0, cfg)
    importlib.invalidate_caches()


@pytest.fixture
def expected_lingering_timers() -> bool:
    # The real PID thermostat keeps a keep-alive timer; the mock house is torn down mid-run.
    return True


@pytest.fixture
def ha(hass, enable_custom_integrations, tmp_path):
    """The pytest-homeassistant `hass`, pointed at a config dir with the real blueprints and the
    real smart_thermostat component."""
    cfg = prepare_config_dir(tmp_path)
    hass.config.config_dir = str(cfg)
    hass.config.latitude, hass.config.longitude = HOME
    _point_custom_components_at(str(cfg))
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)
    yield hass
    if str(cfg) in sys.path:
        sys.path.remove(str(cfg))


@pytest.fixture(autouse=True)
def clock(freezer):
    """One frozen clock per test, shared by every house the test boots (restarts included)."""
    from . import harness

    harness.CLOCK = freezer
    yield freezer
    harness.CLOCK = None
