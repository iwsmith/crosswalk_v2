import logging
import subprocess

from pydantic import BaseModel
from xwalk2.util import SubscribeComponent, ImageLibrary
from xwalk2.models import PlayScene, EndScene
# ./led-image-viewer --led-cols=64 --led-chain=2 --led-gpio-mapping=adafruit-hat-pwm --led-pwm-lsb-nanoseconds=50 --led-show-refresh --led-pixel-mapper "U-mapper;Rotate:90" -l 1  countdown3.gif

VIEWER_COMMAND = [
    "led-image-viewer",
    "--led-cols=64",
    "--led-chain=2",
    "--led-gpio-mapping=adafruit-hat-pwm",
    "--led-pwm-lsb-nanoseconds=400",
    '--led-pixel-mapper "U-mapper;Rotate:90"',  # TODO: Add rotate in here
]

logger = logging.getLogger(__name__)


class MatrixViewer(SubscribeComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        image_root: str,
        subscribe_address="tcp://127.0.0.1:5557",
    ) -> None:
        super().__init__(component_name, host_name, subscribe_address)
        self.animations = ImageLibrary(image_root)
        self._process = None

    def _display_command(self, animation, forever=False):
        """
        Return a list of command line arguments for showing the animated image.
        """
        args = []
        args.extend(VIEWER_COMMAND)
        if not forever:
            args.append("-l 1") # Note: `l=1` doesn't work, `l 1` does
        args.append(str(self.animations[animation]))
        return args

    def kill(self):
        """Kill the currently playing animation, if any."""
        if self._process:
            # logger.debug("Killing: %s", self.playing())
            subprocess.call(["/usr/bin/pkill", "-P", str(self._process.pid)])
            self._process.kill()
            self._process = None
        self._playing = None

    def _exec(self, command, shell=False):
        """Execute a new subprocess command."""
        self.kill()
        logger.debug("Executing: %s", command)
        self._process = subprocess.Popen(command, shell=shell)

    def play(self, animation):
        """
        Play the given animation. Any currently playing image will be replaced.
        """
        self.kill()

        if animation is None:
            return

        command = self._display_command(animation, forever=True)

        logger.info("Playing: %s", animation)
        self._exec(command)
        self._playing = [animation]

    def process_message(self, message: BaseModel):
        if isinstance(message, PlayScene):
            self.play_all([message.intro, message.walk, message.outro])
        elif isinstance(message, EndScene):
            self.play


    def play_all(self, animations):
        """
        Play the given animations in sequence. Any currently playing image will
        be replaced.
        """
        self.kill()

        animations = [image for image in animations if image]

        if not animations:
            return

        commands = [" ".join(self._display_command(image)) for image in animations]

        script = " && ".join(commands)

        logger.info("Playing all: %s", [image for image in animations])
        logger.info("Script: %s", script)
        self._exec(script, shell=True)
        self._playing = animations

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir")
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set the logging level'
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    m = MatrixViewer("matrix-viewer", "crosswalk-a", args.image_dir)
    m.run()