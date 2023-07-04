import logging
import logging.config
from subprocess import Popen
from typing import Optional

from lacus.default import AbstractManager, get_config, get_homedir

logging.config.dictConfig(get_config("logging"))


class Website(AbstractManager):
    def __init__(self, loglevel: Optional[int] = None):
        """
        Initialize the Website manager.

        Args:
            loglevel (Optional[int]): Optional log level for the manager. Defaults to None.
        """
        super().__init__(loglevel)
        self.script_name = "website"
        self.process = self._launch_website()
        self.set_running()

    def _launch_website(self) -> Popen:
        """
        Launch the website process.

        Returns
        -------
            Popen: The subprocess.Popen object representing the launched process.
        """
        website_dir = get_homedir() / "website"
        ip = get_config("generic", "website_listen_ip")
        port = get_config("generic", "website_listen_port")
        return Popen(
            [
                "gunicorn",
                "-w",
                "10",
                "--graceful-timeout",
                "2",
                "--timeout",
                "300",
                "-b",
                f"{ip}:{port}",
                "--log-level",
                "info",
                "web:app",
            ],
            cwd=website_dir,
        )


def main() -> None:
    """
    Entry point for the program.

    Creates an instance of the Website manager and runs it with a specified sleep duration.
    """
    w = Website()
    w.run(sleep_in_sec=10)


if __name__ == "__main__":
    main()
