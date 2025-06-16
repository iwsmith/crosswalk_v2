import yaml
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import os
import wave
import mutagen


class AnimationLibrary:
    """Manages animation selection based on weighted schedules from config.yaml"""
    
    def __init__(self, config_path: str = "test/data/config.yaml"):
        """Initialize library by loading config file"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.img_base_path = Path("test/data/img")
        self.snd_base_path = Path("test/data/snd")
        
        # Cache for audio durations
        self._duration_cache: Dict[str, float] = {}
        
    def _load_config(self) -> dict:
        """Load and parse the config.yaml file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {self.config_path}: {e}")
    
    def get_current_weights(self) -> Dict[str, int]:
        """Determine which weight set to use based on current time and schedule"""
        # For now, use 'demo' as default
        # TODO: Implement proper schedule-based weight selection
        weights = self.config.get('weights', {})
        return weights.get('demo', weights.get('all', {'_': 1}))
    
    def select_intro(self) -> str:
        """Select a random intro animation with even distribution"""
        intros = self.config.get('intros', [])
        if not intros:
            # Fallback to available files
            intro_dir = self.img_base_path / "intros"
            if intro_dir.exists():
                intros = [f.stem for f in intro_dir.glob("*.gif")]
        
        if not intros:
            raise RuntimeError("No intro animations available")
            
        # Random selection with even distribution
        return np.random.choice(intros)
    
    def select_walk(self) -> str:
        """Select a random walk animation based on current weights"""
        walks = self.config.get('walks', {})
        if not walks:
            # Fallback to available files
            walk_dir = self.img_base_path / "walks"
            if walk_dir.exists():
                walk_names = [f.stem for f in walk_dir.glob("*.gif")]
                return np.random.choice(walk_names) if walk_names else "walk"
        
        # Extract walk names and their weights based on categories
        weights = self.get_current_weights()
        walk_names = []
        walk_weights = []
        
        for walk_name, walk_info in walks.items():
            walk_names.append(walk_name)
            category = walk_info.get('category', 'normal')
            weight = weights.get(category, 1)
            walk_weights.append(weight)
        
        if not walk_names:
            raise RuntimeError("No walk animations available")
            
        # Normalize weights
        walk_weights = np.array(walk_weights, dtype=float)
        if walk_weights.sum() == 0:
            walk_weights = np.ones(len(walk_weights))
        walk_weights = walk_weights / walk_weights.sum()
        
        return np.random.choice(walk_names, p=walk_weights)
    
    def select_outro(self) -> str:
        """Select a random outro animation with even distribution"""
        outros = self.config.get('outros', [])
        if not outros:
            # Fallback to available files
            outro_dir = self.img_base_path / "outros"
            if outro_dir.exists():
                outros = [f.stem for f in outro_dir.glob("*.gif")]
        
        if not outros:
            raise RuntimeError("No outro animations available")
            
        # Random selection with even distribution
        return np.random.choice(outros)
    
    def get_audio_duration(self, filename: str) -> float:
        """Get duration of audio file in seconds"""
        if filename in self._duration_cache:
            return self._duration_cache[filename]
        
        # Try different audio file extensions
        for ext in ['.mp3', '.m4a', '.wav']:
            audio_path = self.snd_base_path / f"{filename}{ext}"
            if audio_path.exists():
                try:
                    # Use mutagen for most audio formats
                    audio_file = mutagen.File(str(audio_path))
                    if audio_file is not None and hasattr(audio_file, 'info'):
                        duration = audio_file.info.length
                    elif ext == '.wav':
                        # Fallback to wave module for WAV files
                        with wave.open(str(audio_path), 'rb') as wav_file:
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
        raise RuntimeError(f"❌ No audio file found for '{filename}' in {self.snd_base_path}. Expected extensions: .mp3, .m4a, .wav")
    
    def get_sequence_durations(self, intro: str, walk: str, outro: str) -> Tuple[float, float, float]:
        """Get individual durations for intro, walk, and outro animations"""
        intro_duration = self.get_audio_duration(intro)
        walk_duration = self.get_audio_duration(walk)
        outro_duration = self.get_audio_duration(outro)
        
        return intro_duration, walk_duration, outro_duration
    
    def calculate_total_duration(self, intro: str, walk: str, outro: str) -> float:
        """Calculate total duration for a complete animation sequence"""
        intro_duration, walk_duration, outro_duration = self.get_sequence_durations(intro, walk, outro)
        return intro_duration + walk_duration + outro_duration
    
    def select_animation_sequence(self) -> Tuple[str, str, str]:
        """Select a complete animation sequence: intro, walk, outro"""
        intro = self.select_intro()
        walk = self.select_walk()
        outro = self.select_outro()
        
        # Get durations for logging
        intro_duration, walk_duration, outro_duration = self.get_sequence_durations(intro, walk, outro)
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
        
        if any(duration is None for duration in [intro_duration, walk_duration, outro_duration]):
            print(f"⚠️  Some animations missing audio files")
        
        return intro, walk, outro
