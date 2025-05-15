#!/usr/bin/env python3

from pathlib import Path
from subprocess import Popen, run

from lacus.default import get_homedir, get_config


def main() -> None:
    # Just fail if the env isn't set.
    get_homedir()
    print('Start backend (redis)...')
    p = run(['run_backend', '--start'])
    p.check_returncode()
    print('done.')
    print('Start website...')
    Popen(['start_website'])
    print('done.')
    print('Start Capture manager...')
    Popen(['capture_manager'])
    print('done.')

    # Is configured, start wireproxies
    if path_to_wireproxy := Path(get_config('generic', 'wireproxy_path')):
        if path_to_wireproxy.exists() and path_to_wireproxy.is_file():
            print('Start wireproxy...')
            Popen(['wireproxy_manager'])
            print('done.')
        else:
            print('Wireproxy executable missing, skipping.')
    else:
        print('Wireproxy not configured, skipping.')


if __name__ == '__main__':
    main()
