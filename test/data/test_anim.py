from xwalk2.animation_library import AnimationLibrary


def test_animation_library():
    """The config loads and exposes a well-formed animation library."""
    library = AnimationLibrary()

    # Core sections are present.
    assert library.config.intros, "expected at least one intro"
    assert library.config.outros, "expected at least one outro"
    assert library.config.walks, "expected walk categories"
    assert "default" in library.config.weights, "weights must include 'default'"

    # The model validator keeps the menu sorted by start time.
    starts = [item.start for item in library.config.menu]
    assert starts == sorted(starts), "menu should be sorted by start time"

    # get_active_schedule returns nothing or one of the known menu items.
    active = library.get_active_schedule()
    assert active is None or active in library.config.menu
