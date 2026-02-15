from unittest.mock import MagicMock

import pytest

import bulbs
from bulbs import BulbInfo


@pytest.fixture(autouse=True)
def clear_bulbs():
    """Ensure bulbs._bulbs is empty before each test."""
    bulbs._bulbs.clear()
    yield
    bulbs._bulbs.clear()


@pytest.fixture
def mock_bulb():
    """A MagicMock mimicking yeelight.Bulb."""
    b = MagicMock()
    b.get_properties.return_value = {
        "power": "on",
        "bright": "80",
        "rgb": "16711680",
        "ct": "4000",
        "color_mode": "2",
    }
    return b


@pytest.fixture
def populated_bulbs(mock_bulb):
    """Populate bulbs._bulbs with a single fake bulb."""
    bulbs._bulbs["desk"] = BulbInfo(bulb=mock_bulb, name="desk", ip="192.168.1.10")
    return bulbs._bulbs
