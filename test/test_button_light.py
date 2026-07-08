from xwalk2.button_light_virtual import ButtonLight
from xwalk2.models import CurrentState, EndScene, PlayScene, WalkDefinition


def make_light():
    return ButtonLight(
        "button_led_test", "test-host", "tcp://subscribe", "tcp://heartbeat"
    )


def a_walk_definition():
    return WalkDefinition(image="walk", audio="walk", duration=1.0)


def test_light_starts_off():
    light = make_light()
    assert light.led.light == "off"


def test_play_scene_turns_light_off():
    light = make_light()
    light.led.on()

    light.process_message(
        PlayScene(
            intro=a_walk_definition(),
            walk=a_walk_definition(),
            outro=a_walk_definition(),
            stop=a_walk_definition(),
            total_duration=3.0,
        )
    )

    assert light.led.light == "off"


def test_end_scene_turns_light_on():
    light = make_light()

    light.process_message(EndScene())

    assert light.led.light == "on"


def test_current_state_walk_turns_light_off():
    light = make_light()
    light.led.on()

    light.process_message(CurrentState(state="walk"))

    assert light.led.light == "off"


def test_current_state_ready_turns_light_on():
    light = make_light()

    light.process_message(CurrentState(state="ready"))

    assert light.led.light == "on"
