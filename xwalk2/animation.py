import logging
import os
import random
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel

import yaml

logger = logging.getLogger(__name__)


class Animation(BaseModel):
    """
    An instruction to show an animated image. The image may be played for a
    fixed number of loops and at a desired speed, and have an audio file
    associated with it.
    """

    name: str
    image_path: str
    audio_path: Optional[str]
    frame_delay: Optional[float]
    loops: Optional[int]
    category: Optional[str]
    skip_intro: bool = False
    skip_outro: bool = False


class Scene:
    """
    A scene is a sequence of animations.
    """

    def __init__(self, animations: List[Animation]):
        """Construct a new scene from the given animations."""
        self.animations = animations

    def __iter__(self):
        """Iterate through the animations in this scene."""
        return iter(self.animations)

    def __str__(self):
        """Render the scene as a string."""
        return "Scene {}".format([image.name for image in self.animations])

    def append(self, animation):
        """Add an animation to this scene.."""
        self.animations.append(animation)
        return self


class Library(BaseModel):
    """
    A library of animations, used to construct new scenes.
    """

    intros: List[Animation]
    walks: List[Animation]
    outros: List[Animation]
    ads: List[Animation]


def load_animations(
    self,
    namespace,
    image_dir,
    audio_dir,
    config=None,
    sounds=None,
    default_sound=None,
    default_loops=1,
) -> List[Animation]:
    """Load a directory of images, returning a list of animations."""
    config = config or {}
    sounds = sounds or {}
    animations = []
    subdir = os.path.join(image_dir, namespace)
    logger.debug("Loading %s images in %s", namespace, subdir)
    for filename in os.listdir(subdir):
        name, ext = os.path.splitext(filename)

        if ext:
            path = os.path.join(subdir, filename)
            cfg = config.get(namespace, {}).get(name, {})
            audio_path = None
            if "audio" in cfg:
                audio_path = os.path.join(audio_dir, cfg["audio"])
            elif name in sounds:
                audio_path = sounds[name]
            elif default_sound is not None:
                audio_path = os.path.join(audio_dir, default_sound)

            animation = Animation(
                name=name,
                image_path=path,
                category=cfg.get("category"),
                frame_delay=cfg.get("frame_delay"),
                loops=cfg.get("loops", default_loops),
                skip_intro=cfg.get("skip_intro", False),
                skip_outro=cfg.get("skip_outro", False),
                audio_path=audio_path,
            )

            if not animation.category:
                logger.warning("No category found for %s", filename)

            animations.append(animation)

    categories = set(
        [animation.category for animation in animations if animation.category]
    )
    logger.info(
        "Loaded %d images across categories: %s",
        len(animations),
        ", ".join(categories),
    )

    return sorted(animations, key=lambda x: x.name)


def build_library(config_path: str, image_path: str, audio_dir: str) -> Library:
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading {config_path} {e}")
        config = {}

    sounds = {
        os.path.splitext(filename)[0]: os.path.join(audio_dir, filename)
        for filename in os.listdir(audio_dir)
    }

    intros = load_animations("intros", config, sounds)
    outros = load_animations("outros", config, sounds)
    walks = load_animations("walks", config, sounds, "walk_now.wav", 5)
    ads = load_animations("ads", config, sounds, default_loops=None)

    return Library(intros=intros, outros=outros, walks=walks, ads=ads)
