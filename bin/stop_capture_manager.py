import argparse
import logging
import logging.config
import signal

import psutil

from lacus.default import get_config

logging.config.dictConfig(get_config("logging"))


def main():
    """
    Entry point for the program.

    This function sends a SIGTERM signal to the capture_manager process to allow for a clean restart.
    It parses command-line arguments using `argparse`, but the arguments are not used in the function.
    It searches for the capture_manager process using `psutil` and sends the signal if found.
    If the capture_manager process is not found, it prints an appropriate message.
    """
    parser = argparse.ArgumentParser(
        description="Sends a SIGTERM to the capture_manager so you can restart it cleanly."
    )
    parser.parse_args()

    found = False
    for p in psutil.process_iter(["name"]):
        if p.name() == "capture_manager":
            p.send_signal(signal.SIGTERM)
            found = True

    if not found:
        print("Unable to find capture_manager")


if __name__ == "__main__":
    main()
