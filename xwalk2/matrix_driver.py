import logging
import os
import subprocess

from pydantic import BaseModel

from xwalk2.models import CurrentState, EndScene, PlayScene
from xwalk2.util import ImageLibrary, SubscribeComponent, add_default_args

# ./led-image-viewer --led-cols=64 --led-chain=2 --led-gpio-mapping=adafruit-hat-pwm --led-pwm-lsb-nanoseconds=50 --led-show-refresh --led-pixel-mapper "U-mapper;Rotate:90" -l 1  countdown3.gif

VIEWER_COMMAND = [
    "led-image-viewer",
    "--led-cols=64",
    "--led-chain=2",
    "--led-gpio-mapping=adafruit-hat-pwm",
    "--led-slowdown-gpio=2",
    "--led-limit-refresh=140",
    "--led-drop-priv-user=crosswalk",
]

ROTATION = os.getenv("XWALK_LED_ANGLE")
SHELL_MAPPER = f'--led-pixel-mapper="U-mapper;Rotate:{ROTATION}"'  # When execing in shell we need to quote
EXEC_MAPPER = f"--led-pixel-mapper=U-mapper;Rotate:{ROTATION}"  # When calling popen without a shell we don't quote

logger = logging.getLogger(__name__)


class MatrixViewer(SubscribeComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        image_root: str,
        subscribe_address: str,
        heartbeat_address: str,
    ) -> None:
        super().__init__(
            component_name, host_name, subscribe_address, heartbeat_address
        )
        self.animations = ImageLibrary(image_root)
        self._process = None
        self._playing = None

    def _display_command(self, animation, shell=False, forever=False):
        """
        Return a list of command line arguments for showing the animated image.
        """
        args = []
        args.extend(VIEWER_COMMAND)
        if shell:
            args.append(SHELL_MAPPER)
        else:
            args.append(EXEC_MAPPER)
        if not forever:
            args.append("-l 1")  # Note: `l=1` doesn't work, `l 1` does
        args.append(str(self.animations[animation]))
        return args

    def kill(self):
        """Kill the currently playing animation, if any."""
        if self._process:
            logger.debug(f"Killing: {self._playing} {self._process.pid}")
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
            logging.info(f"{animation=}")
            return

        command = self._display_command(animation, shell=False, forever=True)
        # command = " ".join(command)

        logger.info("Playing: %s", animation)
        self._exec(command)
        self._playing = [animation]

    def process_message(self, message: BaseModel):
        if isinstance(message, PlayScene):
            #self.play_all([message.intro, message.walk, message.outro, message.stop])
            self.play(message.walk)
        elif isinstance(message, EndScene):
            if self._playing != ['stop']:
                self.play("stop")
        elif isinstance(message, CurrentState):
            logger.info("Got CurrentState")
            if message.state == "ready" and self._playing != ['stop']:
                self.play("stop")

    def play_all(self, animations):
        """
        Play the given animations in sequence. Any currently playing image will
        be replaced.
        """
        self.kill()

        if not animations:
            return

        commands = []
        for image in animations:
            forever = False
            if image == "stop":
                forever = True

            commands.append(
                " ".join(self._display_command(image, shell=True, forever=forever))
            )

        script = " && ".join(commands)

        logger.info("Playing all: %s", animations)
        logger.debug("Script: %s", script)
        self._exec(script, shell=True)
        self._playing = animations


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir")

    add_default_args(parser)

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    m = MatrixViewer(
        "matrix-viewer", args.hostname, args.image_dir, args.controller, args.heartbeat
    )
    m.run()
