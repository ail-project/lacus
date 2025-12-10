#!/usr/bin/env python3

from __future__ import annotations

import os
import sys

from subprocess import run

import orjson

from lacus.default import get_homedir

# The script requires this GO project: https://github.com/hatemosphere/protonvpn-wg-config-generate


def get_configs() -> None:
    config_file = get_homedir() / 'tools' / 'protonvpn_generate_config.json'
    if not config_file.exists():
        print(f"Missing config file: {config_file}")
        sys.exit()

    with config_file.open('rb') as f:
        c = orjson.loads(f.read())

    script_path = c['script_path']
    if not os.path.exists(script_path):
        print(f"Path to the script to generate the WG config files doesn't exist: {script_path}")
        sys.exit()

    username = c['username']

    print('If you see a password prompt, enter the password of your ProtonVPN account.')

    for cc, name in c['countries'].items():
        wg_config_path = get_homedir() / 'config' / f'{name}.conf'
        if wg_config_path.exists():
            print(f"A config file for {cc} - {name} already exists, skipping.")
            continue
        to_run = [script_path, '-username', username, '-countries', cc, '-output', str(wg_config_path)]
        p = run(to_run)
        print(p.stdout)


if __name__ == "__main__":
    get_configs()
