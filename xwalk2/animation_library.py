import logging
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import random
import mutagen
import numpy as np
import yaml
from datetime import datetime

from xwalk2.models import Animations, WeightSchedule

logger = logging.getLogger(__name__)


class AnimationLibrary:
    """Manages animation selection based on weighted schedules from config.yaml"""

    def __init__(self, config_path: str = "test/data/config.yaml"):
        """Initialize library by loading config file"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        logger.info(
            f"Loaded {len(self.config.intros)} intros, {len(self.config.walks)} walks, {len(self.config.outros)} outros from {self.config_path}"
        )
        self.img_base_path = Path("test/data/img")
        self.snd_base_path = Path("test/data/snd")

        # Cache for audio durations
        self._duration_cache: Dict[str, float] = {}

    def _load_config(self) -> Animations:
        """Load and parse the config.yaml file"""
        try:
            with open(self.config_path, "r") as f:
                return Animations(**yaml.safe_load(f))
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {self.config_path}: {e}")
    
    def get_current_weights(self) -> WeightSchedule:
        """Determine which weight set to use based on the current time and schedule."""
        now = datetime.now()
        menu = self.config.menu

        active_schedule = None
        latest_start_time = None

        for schedule in menu:
            if schedule.start <= now:
                if latest_start_time is None or schedule.start > latest_start_time:
                    latest_start_time = schedule.start
                    active_schedule = schedule
        
        weights = self.config.weights['default']
        
        if active_schedule:
            logger.info(f"Active schedule: {active_schedule}")
            weights_name = active_schedule.weights
            weights = self.config.weights[weights_name]

        # No active schedule; fallback to demo or default.
        return weights
    
    def select_intro(self, walk: Optional[str] = None) -> str:
        """
        Select a random* intro animation with even distribution
        
        * Not random, if we are selecting the intro based on a given walk.
        """
        # If the walk starts with "walk-" then we need to select an intro that
        # matches the walk name except instead of "walk" it says "wait" e.g.
        # "walk-danish" -> "wait-danish"
        if walk and walk.startswith("walk-"):
            # Matching intros should have the same name as the walk except
            # instead of "walk" it says "wait" e.g. "walk-danish" -> "wait-danish"
            return walk.replace("walk-", "wait-")
        else: 
            # Random selection with even distribution
            return np.random.choice(self.config.intros)

    def select_walk(self) -> str:
        """Select a random walk animation based on current weights"""
        # Extract walk names and their weights based on categories
        weights = self.get_current_weights()
        categories = list(weights.keys())
        cat_weights = np.array(list(weights.values()), dtype=np.float32)
        cat_weights /= cat_weights.sum()  # Normalize weights
        category = np.random.choice(categories, p=cat_weights)

        walk_names = [name for name, info in self.config.walks.items() if info.category == category]
        logger.info(f"Selected walk category: {category}, found {len(walk_names)} walks")

        if not walk_names:
            raise RuntimeError("No walk animations available")

        # Normalize weights
        return random.choice(walk_names)

    def select_outro(self) -> str:
        """Select a random outro animation with even distribution"""

        if not self.config.outros:
            raise RuntimeError("No outro animations available")

        # Random selection with even distribution
        return np.random.choice(self.config.outros)

    def get_audio_duration(self, filename: str) -> float:
        """Get duration of audio file in seconds"""
        if filename in self._duration_cache:
            return self._duration_cache[filename]

        # Try different audio file extensions
        for ext in [".mp3", ".m4a", ".wav"]:
            audio_path = self.snd_base_path / f"{filename}{ext}"
            if audio_path.exists():
                try:
                    # Use mutagen for most audio formats
                    audio_file = mutagen.File(str(audio_path))
                    if audio_file is not None and hasattr(audio_file, "info"):
                        duration = audio_file.info.length
                    elif ext == ".wav":
                        # Fallback to wave module for WAV files
                        with wave.open(str(audio_path), "rb") as wav_file:
                            frames = wav_file.getnframes()
                            rate = wav_file.getframerate()
                            duration = frames / float(rate)
                    else:
                        continue  # Try next extension

                    self._duration_cache[filename] = duration
                    return duration
                except Exception as e:
                    print(f"⚠️  Warning: Could not read {audio_path.name}: {e}")
                    continue

        # Raise error if no audio file found since all animations should have audio
        raise RuntimeError(
            f"❌ No audio file found for '{filename}' in {self.snd_base_path}. Expected extensions: .mp3, .m4a, .wav"
        )

    def get_sequence_durations(
        self, intro: str, walk: str, outro: str
    ) -> Tuple[float, float, float]:
        """Get individual durations for intro, walk, and outro animations"""
        intro_duration = self.get_audio_duration(intro)
        walk_duration = self.get_audio_duration(walk)
        outro_duration = self.get_audio_duration(outro)

        return intro_duration, walk_duration, outro_duration

    def calculate_total_duration(self, intro: str, walk: str, outro: str) -> float:
        """Calculate total duration for a complete animation sequence"""
        intro_duration, walk_duration, outro_duration = self.get_sequence_durations(
            intro, walk, outro
        )
        return intro_duration + walk_duration + outro_duration

    def select_animation_sequence(self) -> Tuple[str, str, str]:
        """
        Select a complete animation sequence: intro, walk, outro

        Walk needs to come first so we can handle language-specific walks
        which have specific intros.
        """
        walk = self.select_walk()
        intro = self.select_intro(walk)
        outro = self.select_outro()

        # Get durations for logging
        intro_duration, walk_duration, outro_duration = self.get_sequence_durations(
            intro, walk, outro
        )
        total_duration = intro_duration + walk_duration + outro_duration

        # Log sequence selection in table format
        print(f"\nAnimation sequence selected:")
        print(f"┌─────────────┬──────────────────────┬──────────────┐")
        print(f"│ Phase       │ Animation            │ Duration     │")
        print(f"├─────────────┼──────────────────────┼──────────────┤")
        print(f"│ Intro       │ {intro:<20} │ {intro_duration:>7.2f}s     │")
        print(f"│ Walk        │ {walk:<20} │ {walk_duration:>7.2f}s     │")
        print(f"│ Outro       │ {outro:<20} │ {outro_duration:>7.2f}s     │")
        print(f"├─────────────┴──────────────────────┼──────────────┤")
        print(f"│ Total                              │ {total_duration:>7.2f}s     │")
        print(f"└────────────────────────────────────┴──────────────┘")

        if any(
            duration is None
            for duration in [intro_duration, walk_duration, outro_duration]
        ):
            print(f"⚠️  Some animations missing audio files")

        return intro, walk, outro
