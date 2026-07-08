from xwalk2.fsm import Controller
from xwalk2.models import EndScene, PlayScene


def make_controller():
    """A Controller wired to a list instead of a real ZMQ socket."""
    sent = []
    controller = Controller(send_message_fn=sent.append)
    return controller, sent


def a_known_walk(controller):
    """Any walk name that actually exists in the loaded animation config."""
    for walks in controller.animations.config.walks.values():
        for name in walks:
            return name
    raise AssertionError("no walks configured")


def test_initial_state_is_ready():
    controller, sent = make_controller()
    assert controller.state == "ready"
    assert controller.walk_queue == []
    assert controller.walk_history == []


def test_button_press_transitions_to_walk_and_emits_play_scene():
    controller, sent = make_controller()

    controller.button_press()

    assert controller.state == "walk"
    assert len(sent) == 1
    assert isinstance(sent[0], PlayScene)


def test_walk_history_records_the_walk_that_played():
    controller, sent = make_controller()

    controller.button_press()

    play_scene = sent[0]
    assert len(controller.walk_history) == 1
    happened_at, walk_name = controller.walk_history[0]
    assert walk_name == play_scene.walk.image


def test_timer_expired_transitions_to_ready_and_emits_end_scene():
    controller, sent = make_controller()
    controller.button_press()
    sent.clear()

    controller.timer_expired()

    assert controller.state == "ready"
    assert len(sent) == 1
    assert isinstance(sent[0], EndScene)


def test_timer_expired_is_ignored_while_already_ready():
    controller, sent = make_controller()

    controller.timer_expired()

    assert controller.state == "ready"
    assert sent == []
    assert controller.walk_history == []


def test_button_press_is_ignored_while_already_walking():
    controller, sent = make_controller()
    controller.button_press()
    sent.clear()

    controller.button_press()

    assert controller.state == "walk"
    assert sent == []
    # No second walk should have been selected/recorded.
    assert len(controller.walk_history) == 1


def test_reset_from_walk_returns_to_ready_and_emits_end_scene():
    controller, sent = make_controller()
    controller.button_press()
    sent.clear()

    controller.reset()

    assert controller.state == "ready"
    assert len(sent) == 1
    assert isinstance(sent[0], EndScene)


def test_reset_from_ready_is_a_noop_transition_that_still_emits_end_scene():
    controller, sent = make_controller()

    controller.reset()

    assert controller.state == "ready"
    assert len(sent) == 1
    assert isinstance(sent[0], EndScene)


def test_queued_known_walk_is_used_and_dequeued():
    controller, sent = make_controller()
    walk = a_known_walk(controller)
    controller.walk_queue.append(walk)

    controller.button_press()

    assert controller.walk_queue == []
    play_scene = sent[0]
    assert play_scene.walk.image == walk


def test_walk_queue_is_consumed_fifo():
    controller, sent = make_controller()
    walks = list(controller.animations.config.walks.values())[0]
    first_two = list(walks)[:2]
    if len(first_two) < 2:
        # Only one walk configured overall; nothing meaningful to order.
        return
    controller.walk_queue.extend(first_two)

    controller.button_press()
    assert sent[0].walk.image == first_two[0]

    controller.timer_expired()
    sent.clear()
    controller.button_press()
    assert sent[0].walk.image == first_two[1]

    assert controller.walk_queue == []


def test_unknown_queued_walk_falls_back_to_a_random_walk_without_crashing():
    controller, sent = make_controller()
    controller.walk_queue.append("this-walk-does-not-exist")

    controller.button_press()

    # The bad entry is still popped off the queue...
    assert controller.walk_queue == []
    # ...and the FSM recovers into 'walk' with a real, playable scene instead
    # of getting stuck or raising.
    assert controller.state == "walk"
    assert len(sent) == 1
    assert isinstance(sent[0], PlayScene)
    assert sent[0].walk.image != "this-walk-does-not-exist"
