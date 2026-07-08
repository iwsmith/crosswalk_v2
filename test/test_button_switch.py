import threading
import time

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from xwalk2.models import ButtonPress


@pytest.fixture(autouse=True)
def mock_gpio():
    """Run against an in-memory pin factory instead of real Pi hardware."""
    Device.pin_factory = MockFactory()
    yield
    Device.pin_factory.reset()


def make_button(monkeypatch, pin=25):
    monkeypatch.setenv("XWALK_BUTTON_PIN", str(pin))
    # Import (and its class body's env var read) must happen after the pin
    # factory is mocked and the env var is set.
    from xwalk2.button_switch import PhysicalButton

    sent = []
    button = PhysicalButton("button_physical", "test-host", "tcp://x", "tcp://y")
    button.send_action = sent.append
    return button, sent


def press_and_release(button, hold_seconds=0.05):
    thread = threading.Thread(target=button.loop, daemon=True)
    thread.start()
    time.sleep(0.02)  # let wait_for_press() start listening
    button.button.pin.drive_low()  # pull_up=True: idle high, press pulls low
    time.sleep(hold_seconds)
    button.button.pin.drive_high()
    time.sleep(0.05)  # let the loop iteration finish and send the message


def test_button_uses_configured_pin(monkeypatch):
    button, _ = make_button(monkeypatch, pin=17)
    assert button.button_pin == 17


def test_button_defaults_to_pin_25(monkeypatch):
    monkeypatch.delenv("XWALK_BUTTON_PIN", raising=False)
    from xwalk2.button_switch import PhysicalButton

    button = PhysicalButton("button_physical", "test-host", "tcp://x", "tcp://y")
    assert button.button_pin == 25


def test_press_and_release_emits_a_single_button_press(monkeypatch):
    button, sent = make_button(monkeypatch)

    press_and_release(button)

    assert len(sent) == 1
    assert isinstance(sent[0], ButtonPress)
    assert sent[0].host == "test-host"
    assert sent[0].component == "button_physical"


def test_press_duration_reflects_how_long_the_button_was_held(monkeypatch):
    button, sent = make_button(monkeypatch)

    press_and_release(button, hold_seconds=0.2)

    assert len(sent) == 1
    # Allow generous slack for scheduling jitter; this just guards against
    # e.g. duration being computed in the wrong units or not at all.
    assert 150 <= sent[0].press_duration <= 500
