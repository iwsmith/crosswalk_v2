from xwalk2.animation_library import AnimationLibrary
import yaml

def test_animation_library():
    """Test the AnimationLibrary class"""
    with open("static/data/config.yaml", "r") as f:
        animations = yaml.safe_load(f)

    library = AnimationLibrary()

    for i in library.config.menu:
        print(i)

    for a in animations['menu']:
        print(a)