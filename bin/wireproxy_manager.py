#!/usr/bin/env python3

from __future__ import annotations

import configparser
import json
import logging
import logging.config
import socket

import requests

from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from subprocess import Popen, PIPE
from urllib.parse import urlparse

from watchdog.events import (PatternMatchingEventHandler, DirCreatedEvent, DirDeletedEvent,
                             FileCreatedEvent, FileDeletedEvent, DirModifiedEvent, FileModifiedEvent)
from watchdog.observers import Observer

from lacus.default import AbstractManager, get_config, get_homedir
from lacus.default.exceptions import ConfigError

logging.config.dictConfig(get_config('logging'))


@dataclass
class WireProxy:

    process: Popen[bytes]
    config_file: Path
    health_endpoint: str
    failed_healthcheck: int = 0

    def is_running(self) -> bool:
        if self.process.poll() is None:
            return True
        return False

    def stop(self) -> None:
        self.process.terminate()

    def is_healthy(self) -> bool:
        try:
            r = requests.get(f'http://{self.health_endpoint}/readyz', timeout=2)
            r.raise_for_status()
            self.failed_healthcheck = 0
        except requests.exceptions.RequestException:
            self.failed_healthcheck += 1
            return False
        return True


class WireProxyFSManager(PatternMatchingEventHandler):

    min_port: int = 25300
    max_port: int = 25399
    default_checkalive: str = '1.1.1.1'
    max_failed_healthcheck = 5
    used_local_ports: dict[int, str] = {}

    def __init__(self, path_to_wireproxy: Path, configs_dir: Path, logger: Logger) -> None:
        super().__init__(ignore_directories=True, case_sensitive=False,
                         patterns=['*.conf', '*proxies.json'])
        self.logger = logger
        self.logger.debug(f"WireProxyManager initialized with path_to_wireproxy: {path_to_wireproxy}, configs_dir: {configs_dir}")
        self.wireproxy = path_to_wireproxy
        self.configs_dir = configs_dir
        self.proxies_config_path = self.configs_dir / "proxies.json"

        self.wireproxies: dict[str, WireProxy] = {}

        self._init_configs()
        self.launch_all_wireproxies()

    def _check_local_port_in_config(self, config_name: str, address: str, port: int | str) -> None:
        if address in ['127.0.0.1', 'localhost']:
            p = int(port)
            if p in self.used_local_ports and self.used_local_ports[p] != config_name:
                raise ConfigError(f"Port {p} already in use by another proxy: {self.used_local_ports[p]}.")
            self.used_local_ports[p] = config_name

    def check_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def _init_configs(self) -> None:
        # Load the lacus proxy config file
        if not self.proxies_config_path.exists():
            self.proxies = {}
        else:
            with self.proxies_config_path.open('r') as f:
                self.proxies = json.load(f)

        for name, p in self.proxies.items():
            if p.get('proxy_url'):
                proxy_url = urlparse(p['proxy_url'])
                self._check_local_port_in_config(name, proxy_url.hostname, proxy_url.port)

        # Load the wireguard configs
        for config_file in self.configs_dir.glob('*.conf'):
            config_name = config_file.stem
            wg_config = configparser.ConfigParser()
            wg_config.read(config_file)
            if socks5_address := wg_config.get('Socks5', 'BindAddress', fallback=None):
                address, _port = socks5_address.split(':')
                self._check_local_port_in_config(config_name, address, _port)

        for config_file in self.configs_dir.glob('*.conf'):
            self._sync_wireguard_proxies(config_file)

    def _sync_wireguard_proxies(self, wiregard_config_path: Path) -> bool:
        config_name = wiregard_config_path.stem
        wg_config = configparser.ConfigParser()
        wg_config.read(wiregard_config_path)
        proxy_config = self.proxies.get(config_name)
        if not proxy_config:
            self.logger.debug(f'New proxy: {config_name}')
            # No proxy config found for this wireguard config
            proxy_config = {'description': f"Proxy for {config_name}",
                            'meta': {'provider': 'wireguard'}
                            }

        wg_config_changed = False
        if proxy_config.get('proxy_url'):
            # Case 1: Proxy config exists in proxy config only
            self.logger.debug(f'Setting proxy {config_name} in {config_name}.')
            proxy_url = urlparse(proxy_config['proxy_url'])
            self._check_local_port_in_config(config_name, proxy_url.hostname, proxy_url.port)
            if wg_config.get('Socks5', 'BindAddress', fallback=None) != proxy_url.netloc:
                wg_config['Socks5'] = {'BindAddress': proxy_url.netloc}
                wg_config_changed = True
        else:
            # Case 2: Proxy config does not exist (create new one)
            # find first unused port in interval
            for port in range(self.min_port, self.max_port):
                if port not in self.used_local_ports and not self.check_port_in_use(port):
                    # got a free port
                    break
            else:
                raise ConfigError(f"No free port found in range {self.min_port}-{self.max_port}")
            self.logger.debug(f'Initialize new proxy URL for {config_name} on port {port}.')
            proxy_config['proxy_url'] = f"socks5://127.0.0.1:{port}"
            wg_config['Socks5'] = {'BindAddress': f'127.0.0.1:{port}'}
            wg_config_changed = True
            self.used_local_ports[port] = config_name

        # Make sure the DNS is set in the proxy config
        if wg_config.get('Interface', 'DNS', fallback=None):
            self.logger.debug(f'Setting DNS resolver for {config_name}.')
            proxy_config['dns_resolver'] = wg_config['Interface']['DNS']

        # Make sure the checkalive is set in the wg config
        if not wg_config.get('Interface', 'CheckAlive', fallback=None):
            self.logger.debug(f'Setting CheckAlive for {config_name}.')
            wg_config['Interface']['CheckAlive'] = self.default_checkalive
            wg_config_changed = True

        if wg_config_changed:
            with wiregard_config_path.open('w') as f:
                wg_config.write(f)

        if self.proxies.get(config_name) != proxy_config:
            # It's been changed
            self.proxies[config_name] = proxy_config
            with self.proxies_config_path.open('w') as f:
                json.dump(self.proxies, f, indent=4, sort_keys=True)
        return wg_config_changed

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        # if wireguard *.conf -> update proxies.json -> initialize wireproxy config
        # if proxies.json -> N/A
        filepath = Path(str(event.src_path))
        if isinstance(event, FileCreatedEvent) and filepath.suffix == '.conf':
            if filepath.stem in self.proxies:
                # If something is runinng with that name, stop it.
                self.logger.info(f'A proxy called {filepath.stem} already exists, stopping it.')
                self.stop_wireproxy(filepath.stem)
            else:
                self.logger.info(f'Got new wireguard config file: {filepath.stem}.')
            try:
                self._sync_wireguard_proxies(filepath)
                self.launch_wireproxy(filepath.stem)
            except ConfigError as e:
                self.logger.warning(f"Unable to create the new proxy: {e}")

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        # NOTE: modification **only** happens in the proxies.json
        # if wireguard *.conf -> N/A
        # if proxies.json -> update wireguard config
        filepath = Path(str(event.src_path))
        if isinstance(event, FileModifiedEvent) and filepath.suffix == '.conf':
            # Modifying the wireproxy config file isn't allowed, but if it happens, we revert it.
            try:
                self.logger.info(f'Wireproxy file modified: {filepath}. Apply the json config')
                if self._sync_wireguard_proxies(filepath):
                    # Do nothing here, the wireproxy config has been reverted, just warn te user.
                    self.stop_wireproxy(filepath.stem)
                    self.launch_wireproxy(filepath.stem)
            except ConfigError as e:
                self.logger.warning(f"Unable to reapply config: {e}")
        elif isinstance(event, FileModifiedEvent) and filepath.name == 'proxies.json':
            with self.proxies_config_path.open('rb') as f:
                proxies = json.loads(f.read())
            if proxies == self.proxies:
                # No changes with what we have in memory
                return

            self.logger.info('Proxies file changed.')
            self.proxies = proxies
            self._init_configs()
            for name in self.proxies.keys():
                filepath = self.configs_dir / f'{name}.conf'
                if not filepath.exists():
                    self.logger.debug(f"Config file for proxy {name} does not exist.")
                    continue
                try:
                    if self._sync_wireguard_proxies(filepath):
                        # it changed, stop ond config & start new one
                        self.stop_wireproxy(name)
                        self.launch_wireproxy(name)
                except ConfigError as e:
                    self.logger.warning(f"Unable to update the proxy: {e}")

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        # if wireguard *.conf -> update proxies.json
        # if proxies.json -> re-run init
        filepath = Path(str(event.src_path))
        if filepath.exists():
            # NOTE: sometimes, modifying the file triggers a delete event
            # But both will be triggered, so the modification will be handled
            # It is safe to ignore.
            self.logger.debug(f'File {filepath} exists, ignoring delete event.')
            return

        if isinstance(event, FileDeletedEvent) and filepath.suffix == '.conf':
            self.logger.info(f'Config file deleted: {filepath}.')
            if self.proxies.pop(filepath.stem, None):
                with self.proxies_config_path.open('w') as f:
                    json.dump(self.proxies, f, indent=4, sort_keys=True)
            self.stop_wireproxy(filepath.stem)
        elif isinstance(event, FileDeletedEvent) and filepath.name == 'proxies.json':
            self.logger.info(f'Proxies file deleted: {filepath}, reseting.')
            self._init_configs()

    def remove_proxy(self, name: str) -> None:
        if self.proxies.pop(name, None):
            with self.proxies_config_path.open('w') as f:
                json.dump(self.proxies, f, indent=4, sort_keys=True)

    # ####  Manage proxy services #### #

    def launch_wireproxy(self, name: str) -> None:
        if name in self.wireproxies:
            self.logger.info(f"Wireproxy for {name} already exists.")
            return

        config_file = self.configs_dir / f'{name}.conf'
        wg_config = configparser.ConfigParser()
        wg_config.read(config_file)

        address, _ = wg_config.get('Socks5', 'BindAddress').split(':')
        for port in range(self.min_port, self.max_port):
            if port not in self.used_local_ports and not self.check_port_in_use(port):
                self.used_local_ports[port] = f'{config_file.stem}_health'
                break
        else:
            raise Exception(f"[Health] No free port found in range {self.min_port}-{self.max_port}")
        health_endpoint = f'{address}:{port}'
        process = Popen([self.wireproxy, '--config', config_file, '--info', health_endpoint], stdout=PIPE, stderr=PIPE)

        self.wireproxies[config_file.stem] = WireProxy(process=process,
                                                       config_file=config_file,
                                                       health_endpoint=health_endpoint)

    def launch_all_wireproxies(self) -> None:
        for config_file in self.configs_dir.glob('*.conf'):
            self.launch_wireproxy(config_file.stem)
        self.logger.info("All wireproxies launched.")

    def stop_wireproxy(self, name: str) -> None:
        if name not in self.wireproxies:
            self.logger.debug(f"Wireproxy {name} is not running.")
            return
        self.wireproxies[name].stop()
        self.wireproxies.pop(name, None)
        self.logger.info(f"Wireproxy for {name} stopped.")

    def stop_all_wireproxies(self) -> None:
        for config_file in self.configs_dir.glob('*.conf'):
            self.stop_wireproxy(config_file.stem)
        self.logger.info("All wireproxies stopped.")

    def clean_used_ports(self) -> None:
        # once everything is running, regularly check which ports are actually un use
        for port in list(self.used_local_ports.keys()):
            if not self.check_port_in_use(port):
                self.used_local_ports.pop(port)


class WireProxyManager(AbstractManager):

    def __init__(self, loglevel: int | None=None) -> None:
        self.script_name = "wireproxymanager"
        super().__init__(loglevel)
        # it is DEBUG by default, which is very verbose
        watchdog_logger = logging.getLogger('watchdog')
        watchdog_logger.setLevel(logging.WARNING)
        urllib3_logger = logging.getLogger('urllib3')
        urllib3_logger.setLevel(logging.WARNING)

        path_to_wireproxy = Path(get_config('generic', 'wireproxy_path'))
        if not path_to_wireproxy.exists() or not path_to_wireproxy.is_file():
            raise ConfigError(f"Wireproxy executable not found at {path_to_wireproxy}.")
        self.configs_dir = get_homedir() / 'config'

        self.wpm = WireProxyFSManager(path_to_wireproxy, self.configs_dir, self.logger)

        self.observer = Observer()
        self.observer.schedule(self.wpm, str(self.configs_dir), recursive=False)
        self.observer.start()

    def _to_run_forever(self) -> None:
        # Monitor the status of the proxies
        for config_file in self.configs_dir.glob('*.conf'):
            if (config_file.stem not in self.wpm.wireproxies
                    or not self.wpm.wireproxies[config_file.stem].is_running()):
                self.logger.info(f'{config_file.stem} is not running.')
                self.wpm.remove_proxy(config_file.stem)
                self.wpm.launch_wireproxy(config_file.stem)
                continue

            self.logger.debug(f'{config_file.stem} is running.')
            if self.wpm.wireproxies[config_file.stem].is_healthy():
                self.logger.debug(f'{config_file.stem} is healthy.')
                pass
            else:
                if self.wpm.wireproxies[config_file.stem].failed_healthcheck > self.wpm.max_failed_healthcheck:
                    self.logger.warning(f'{config_file.stem} failed too many healthcheck.')
                    self.wpm.stop_wireproxy(config_file.stem)
                    self.wpm.remove_proxy(config_file.stem)
                else:
                    self.logger.info(f'{config_file.stem} failed healthcheck, retry later.')
        self.wpm.clean_used_ports()

    def _wait_to_finish(self) -> None:
        self.observer.stop()
        self.observer.join()
        self.wpm.stop_all_wireproxies()


def main() -> None:
    wpm = WireProxyManager(loglevel=logging.INFO)
    wpm.run(sleep_in_sec=30)


if __name__ == "__main__":
    main()
