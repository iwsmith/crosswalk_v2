import logging
import random
import wave
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mutagen
import numpy as np
import yaml

from xwalk2.models import Animations, WeightSchedule, MenuItem

logger = logging.getLogger(__name__)


class AnimationLibrary:
    """Manages animation selection based on weighted schedules from config.yaml"""

    def __init__(self, config_path: str = "static/data/config.yaml"):
        """Initialize library by loading config file"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        logger.info(
            f"Loaded {len(self.config.intros)} intros, {len(self.config.walks)} walks, {len(self.config.outros)} outros from {self.config_path}"
        )
        self.img_base_path = Path("static/data/img")
        self.snd_base_path = Path("static/data/snd")

        # Cache for audio durations
        self._duration_cache: Dict[str, float] = {}

        # History for reselection cooldowns
        self.walk_history = deque(maxlen=self.config.reselection.walk_cooldown)
        self.category_history = deque(maxlen=self.config.reselection.category_cooldown)

    def _load_config(self) -> Animations:
        """Load and parse the config.yaml file"""
        try:
            with open(self.config_path, "r") as f:
                return Animations(**yaml.safe_load(f))
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {self.config_path}: {e}")

    def get_active_schedule(self) -> Optional[MenuItem]:
        now = datetime.now()

        active_schedule = None
        latest_start_time = None

        for schedule in self.config.menu:
            if schedule.start <= now:
                if latest_start_time is None or schedule.start > latest_start_time:
                    latest_start_time = schedule.start
                    active_schedule = schedule

        return active_schedule

    def get_current_weights(self) -> WeightSchedule:
        """Determine which weight set to use based on the current time and schedule."""

        active_schedule = self.get_active_schedule()

        weights = self.config.weights["default"]

        if active_schedule:
            logger.info(f"Active schedule: {active_schedule}")
            weights_name = active_schedule.weights
            weights = self.config.weights[weights_name]

        # No active schedule; fallback to demo or default.
        return weights

    def _get_eligible_items(
        self,
        items: List[str],
        history: deque,
        is_exempt_fn: callable,
        item_type: str,
    ) -> List[str]:
        """Filters items to exclude those on cooldown, unless exempt."""
        eligible = [
            item for item in items if is_exempt_fn(item) or item not in history
        ]
        if not eligible and items:
            logger.warning(
                f"All {item_type}s are on cooldown; ignoring cooldown for this selection."
            )
            return items
        return eligible

    def _get_eligible_walks(self, walks: List[str]) -> List[str]:
        """Filter walks based on reselection cooldown."""
        return self._get_eligible_items(
            walks,
            self.walk_history,
            lambda walk: self.config.walks[walk].ignore_reselection,
            "walk",
        )

    def _get_eligible_categories(self, categories: List[str]) -> List[str]:
        """Filter categories based on reselection cooldown."""
        cooldown_cats = self.config.reselection.cooldown_categories
        return self._get_eligible_items(
            categories,
            self.category_history,
            lambda cat: cat not in cooldown_cats,
            "category",
        )

    def _select_weighted_category(
        self, categories: List[str], weights: WeightSchedule
    ) -> str:
        """Selects a category based on the provided weights."""
        eligible_weights = np.array(
            [weights[cat] for cat in categories], dtype=np.float32
        )
        eligible_weights /= eligible_weights.sum()  # Normalize to sum to 1
        return np.random.choice(categories, p=eligible_weights)

    def _update_histories(self, walk: str):
        """Update walk and category histories for cooldown tracking."""
        self.walk_history.append(walk)
        walk_info = self.config.walks.get(walk)
        if (
            walk_info
            and walk_info.category in self.config.reselection.cooldown_categories
        ):
            self.category_history.append(walk_info.category)

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

    def select_walk(self, max_retries: int = 5) -> str:
        """
        Select a random walk, retrying if a valid selection isn't made.
        """
        for attempt in range(max_retries):
            weights = self.get_current_weights()
            categories = list(weights.keys())

            # Case 1: Default weights are used ("_"), select from all walks.
            if len(categories) == 1 and categories[0] == "_":
                all_walks = list(self.config.walks.keys())
                if not all_walks:
                    raise RuntimeError("No walks are defined in config.yaml.")
                
                eligible_walks = self._get_eligible_walks(all_walks)
                
                # This state should not be reachable due to _get_eligible_walks logic
                if not eligible_walks:
                    raise RuntimeError("No eligible walks available even after ignoring cooldowns.")

                selected_walk = random.choice(eligible_walks)
                self._update_histories(selected_walk)
                logger.info(f"Selected from all walks: {selected_walk}")
                return selected_walk

            # Case 2: Category-based selection.
            # Filter for categories that are actually defined in the walks section.
            categories_with_walks = {info.category for info in self.config.walks.values()}
            valid_categories = [cat for cat in categories if cat in categories_with_walks]

            if not valid_categories:
                raise RuntimeError("No walks found for any categories in the current schedule.")

            eligible_categories = self._get_eligible_categories(valid_categories)
            selected_category = self._select_weighted_category(eligible_categories, weights)
            
            walks_in_category = [
                name for name, info in self.config.walks.items() 
                if info.category == selected_category
            ]
            
            # This check is technically redundant now, but good for safety.
            if not walks_in_category:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries}: "
                    f"Selected category '{selected_category}' has no walks. Retrying."
                )
                continue

            eligible_walks = self._get_eligible_walks(walks_in_category)
            if not eligible_walks:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries}: "
                    f"No eligible walks in '{selected_category}' due to cooldowns. Retrying."
                )
                continue

            selected_walk = random.choice(eligible_walks)
            self._update_histories(selected_walk)
            logger.info(f"Selected walk '{selected_walk}' from category '{selected_category}'")
            return selected_walk

        logger.warning(
            f"Failed to select a walk after {max_retries} attempts. "
            "Falling back to standard walk."
        )
        fallback_walk = "walk"
        if fallback_walk not in self.config.walks:
            raise RuntimeError(
                f"Fallback walk '{fallback_walk}' not found in configuration."
            )

        self._update_histories(fallback_walk)
        return fallback_walk

    def select_outro(self) -> str:
        """Select a random outro animation with even distribution"""

        if not self.config.outros:
            raise RuntimeError("No outro animations available")

        # Random selection with even distribution
        return np.random.choice(self.config.outros)

    def get_audio_duration(self, animation_name: str) -> float:
        """
        Get duration of an audio file in seconds.
        If the animation has a custom audio name, use it.
        Otherwise, use the animation name itself as the filename.
        """
        # Check if the animation is a walk and has a custom audio file
        walk_info = self.config.walks.get(animation_name)
        if walk_info and walk_info.audio:
            filename = walk_info.audio
        else:
            filename = animation_name

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

    def select_animation_sequence(
        self, walk: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """
        Select a complete animation sequence: intro, walk, outro

        Walk needs to come first so we can handle language-specific walks
        which have specific intros.
        """
        if not walk:
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
