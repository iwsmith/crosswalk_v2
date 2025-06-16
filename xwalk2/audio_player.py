import logging
import subprocess

from pydantic import BaseModel

from xwalk2.models import EndScene, PlayScene
from xwalk2.util import AudioLibrary, SubscribeComponent

MPG123_COMMAND = ["mpg123", "-o", "alsa"]

logger = logging.getLogger(__name__)


class AudioPlayer(SubscribeComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        audio_root: str,
        subscribe_address="tcp://127.0.0.1:5557",
    ) -> None:
        super().__init__(component_name, host_name, subscribe_address)
        self.audio = AudioLibrary(audio_root)
        self._process = None

    def process_message(self, message: BaseModel):
        if isinstance(message, PlayScene):
            self.play_all([message.intro, message.walk, message.outro])

    def _build_command(self, animation, forever=False):
        """
        Return a list of command line arguments for showing the animated image.
        """
        args = []
        args.extend(MPG123_COMMAND)
        args.append(str(self.audio[animation]))
        return args

    def _exec(self, command, shell=False):
        """Execute a new subprocess command."""
        self.kill()
        logger.debug("Executing: %s", command)
        self._process = subprocess.Popen(command, shell=shell)

    def kill(self):
        if self._process:
            # logger.debug("Killing: %s", self.playing())
            subprocess.call(["/usr/bin/pkill", "-P", str(self._process.pid)])
            self._process.kill()
            self._process = None
        self._playing = None

    def play(self, audio):
        self.kill()

        if audio is None:
            return

        command = self._build_command(audio)
        logger.info("Playing: %s", audio)
        self._exec(command)
        self._playing = [audio]

    def play_all(self, audios):
        self.kill()

        commands = [" ".join(self._build_command(image)) for image in audios]

        script = " && ".join(commands)

        logger.info("Playing all: %s", audios)
        logger.info("Script: %s", script)
        self._exec(script, shell=True)
        self._playing = audios


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("audio_dir")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    a = AudioPlayer("audio-player", "crosswalk-a", args.audio_dir)
    a.run()
