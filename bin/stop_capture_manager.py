#!/usr/bin/env python3

import argparse
import logging
import logging.config

import psutil
import signal

from lacus.default import get_config

logging.config.dictConfig(get_config('logging'))


def main() -> None:
    parser = argparse.ArgumentParser(description='Sends a SIGTERM to the capture_manager so you can restart it cleanly.')
    parser.parse_args()

    found = False
    for p in psutil.process_iter(['name']):
        if p.name() == "capture_manager":
            p.send_signal(signal.SIGTERM)
            found = True

    if not found:
        print('Unable to find capture_manager')


if __name__ == '__main__':
    main()
