import zmq
import json
import time
import threading
import signal
import sys
from pathlib import Path
from typing import Optional, List, Tuple
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import Canvas

from xwalk2.util import heatbeat
from xwalk2.models import PlayScene, ResetCommand, parse_message


# Constants
MATRIX_SIZE = 64
GUI_SIZE = 512  # 8x scaling for visibility
IMG_BASE_PATH = Path("test/data/img")
IMG_SUBDIRS = ["intros", "walks", "outros"]


class GIFPlayer:
    """Handles GIF loading and frame extraction with caching"""
    
    def __init__(self, img_base_path: Path = IMG_BASE_PATH):
        self.img_base_path = img_base_path
        self._cache = {}
    
    def load_gif(self, filename: str) -> Tuple[List[Image.Image], List[float]]:
        """Load GIF file and return (frames, frame_durations)"""
        if filename in self._cache:
            return self._cache[filename]
        
        gif_path = self._find_gif_path(filename)
        if gif_path:
            try:
                result = self._extract_frames(gif_path)
                self._cache[filename] = result
                print(f"📁 Loaded {gif_path.name}: {len(result[0])} frames")
                return result
            except Exception as e:
                print(f"❌ Error loading GIF {gif_path}: {e}")
        
        # Return default black frame
        return self._default_frame(filename)
    
    def _find_gif_path(self, filename: str) -> Optional[Path]:
        """Find GIF file in various subdirectories"""
        possible_paths = [self.img_base_path / f"{filename}.gif"]
        possible_paths.extend(
            self.img_base_path / subdir / f"{filename}.gif" 
            for subdir in IMG_SUBDIRS
        )
        
        return next((path for path in possible_paths if path.exists()), None)
    
    def _extract_frames(self, gif_path: Path) -> Tuple[List[Image.Image], List[float]]:
        """Extract frames and durations from GIF"""
        frames = []
        durations = []
        
        with Image.open(gif_path) as gif:
            for frame_num in range(gif.n_frames):
                gif.seek(frame_num)
                
                # Get frame duration (default 100ms if not specified)
                duration_ms = gif.info.get('duration', 100)
                durations.append(duration_ms / 1000.0)
                
                # Resize for LED matrix
                frame = gif.copy().resize((MATRIX_SIZE, MATRIX_SIZE), Image.Resampling.NEAREST)
                frames.append(frame)
        
        return frames, durations
    
    def _default_frame(self, filename: str) -> Tuple[List[Image.Image], List[float]]:
        """Create default black frame when GIF not found"""
        default_frame = Image.new('RGB', (MATRIX_SIZE, MATRIX_SIZE), color='black')
        result = ([default_frame], [0.1])
        self._cache[filename] = result
        print(f"⚠️  GIF not found for {filename}, using black frame")
        return result


class MatrixDisplay:
    """Matrix display with GUI console interface"""
    
    def __init__(self, console_mode: bool = True):
        self.console_mode = console_mode
        self.gif_player = GIFPlayer()
        self.animation_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # GUI components (console mode)
        self.root: Optional[tk.Tk] = None
        self.canvas: Optional[Canvas] = None
        
        if console_mode:
            self._setup_gui()
    
    def _setup_gui(self):
        """Setup tkinter GUI for console testing"""
        self.root = tk.Tk()
        self.root.title("Crosswalk Matrix Display")
        self.root.geometry(f"{GUI_SIZE + 50}x{GUI_SIZE + 100}")
        self.root.configure(bg='black')
        
        # Create canvas for matrix display
        self.canvas = Canvas(
            self.root, 
            width=GUI_SIZE, 
            height=GUI_SIZE, 
            bg='black', 
            highlightthickness=0
        )
        self.canvas.pack(pady=10)
        
        # Status label
        self.status_label = tk.Label(
            self.root, 
            text="WAIT", 
            font=('Arial', 14, 'bold'), 
            fg='white', 
            bg='black'
        )
        self.status_label.pack(pady=5)
        
        # Show initial state
        self.show_idle()
    
    def show_idle(self):
        """Show idle/wait state"""
        print("🚏 WAIT")
        if self.console_mode and self.status_label:
            self.status_label.config(text="WAIT", fg='white')
        self.display_gif("stop")
    
    def show_walk(self):
        """Show walk state"""
        print("🚶 WALK SIGN IS ON")
        if self.console_mode and self.status_label:
            self.status_label.config(text="WALK SIGN IS ON", fg='green')
    
    def display_gif(self, animation_name: str):
        """Display a GIF animation"""
        if self.animation_thread and self.animation_thread.is_alive():
            self.stop_event.set()
            self.animation_thread.join(timeout=1.0)
        
        self.stop_event.clear()
        self.animation_thread = threading.Thread(
            target=self._animation_worker, 
            args=(animation_name,), 
            daemon=True
        )
        self.animation_thread.start()
    
    def play_scene_sequence(self, intro: str, walk: str, outro: str):
        """Play a complete animation sequence"""
        print(f"🎬 Playing sequence: {intro} -> {walk} -> {outro}")
        
        if self.animation_thread and self.animation_thread.is_alive():
            self.stop_event.set()
            self.animation_thread.join(timeout=1.0)
        
        self.stop_event.clear()
        self.animation_thread = threading.Thread(
            target=self._sequence_worker, 
            args=(intro, walk, outro), 
            daemon=True
        )
        self.animation_thread.start()
    
    def _animation_worker(self, animation_name: str):
        """Worker thread for single animation"""
        frames, durations = self.gif_player.load_gif(animation_name)
        
        while not self.stop_event.is_set():
            for frame, duration in zip(frames, durations):
                if self.stop_event.is_set():
                    break
                self._display_frame(frame)
                time.sleep(duration)
    
    def _sequence_worker(self, intro: str, walk: str, outro: str):
        """Worker thread for animation sequence"""
        sequence = [intro, walk, outro]
        
        for anim_name in sequence:
            if self.stop_event.is_set():
                break
            
            frames, durations = self.gif_player.load_gif(anim_name)
            
            for frame, duration in zip(frames, durations):
                if self.stop_event.is_set():
                    break
                self._display_frame(frame)
                time.sleep(duration)
    
    def _display_frame(self, frame: Image.Image):
        """Display a single frame"""
        if not self.console_mode:
            return  # LED matrix mode would go here
        
        if self.canvas and self.root:
            # Convert PIL image to tkinter format
            tk_image = ImageTk.PhotoImage(frame.resize((GUI_SIZE, GUI_SIZE), Image.Resampling.NEAREST))
            
            # Update canvas on main thread
            def update_canvas():
                self.canvas.delete("all")
                self.canvas.create_image(GUI_SIZE//2, GUI_SIZE//2, image=tk_image)
                self.canvas.image = tk_image  # Keep reference
            
            self.root.after(0, update_canvas)
    
    def close(self):
        """Clean up resources"""
        self.stop_event.set()
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_thread.join(timeout=2.0)
        
        if self.root:
            self.root.quit()


def main():
    """Matrix driver main function with command parsing"""
    print("Starting Matrix Driver...")
    
    # Initialize display (use console mode for testing)
    display = MatrixDisplay(console_mode=True)
    
    # Socket to receive commands
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://127.0.0.1:5557")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages
    
    # Start heartbeat
    heartbeat_thread = heatbeat("matrix_driver", "crosswalk-a")
    
    print("Matrix driver ready. Listening for commands...")
    
    # Setup GUI close handler
    if display.root:
        def on_closing():
            print("🔒 GUI closing...")
            display.close()
            try:
                heartbeat_thread.stop()
                socket.close()
                context.term()
            except:
                pass
            sys.exit(0)
        
        display.root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Command processing thread
    def command_worker():
        try:
            while True:
                try:
                    command = socket.recv_string(zmq.NOBLOCK)
                    print(f"📨 Received: {command}")
                    
                    try:
                        command_obj = parse_message(command)
                        
                        if isinstance(command_obj, PlayScene):
                            print(f"🎬 Play scene command: {command_obj.intro} -> {command_obj.walk} -> {command_obj.outro}")
                            display.show_walk()
                            display.play_scene_sequence(command_obj.intro, command_obj.walk, command_obj.outro)
                        
                        elif isinstance(command_obj, ResetCommand):
                            print("🔄 Reset command")
                            display.show_idle()
                        
                        else:
                            print(f"📋 Other command: {type(command_obj).__name__}")
                            
                    except (json.JSONDecodeError, ValueError) as e:
                        print(f"❓ Invalid command format: {command} (Error: {e})")
                        
                except zmq.Again:
                    time.sleep(0.1)  # No message available
                except zmq.ZMQError as e:
                    print(f"💥 ZMQ error: {e}")
                    break
                    
        except Exception as e:
            print(f"💥 Command worker error: {e}")
    
    # Start command processing thread
    command_thread = threading.Thread(target=command_worker, daemon=True)
    command_thread.start()
    
    try:
        if display.root:
            # Run GUI main loop
            display.root.mainloop()
        else:
            # Non-GUI mode
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down matrix driver...")
    finally:
        display.close()
        try:
            heartbeat_thread.stop()
            socket.close()
            context.term()
        except:
            pass
        print("✅ Matrix driver shutdown complete")


if __name__ == "__main__":
    main()
