#!/usr/bin/env python3

from __future__ import annotations

import logging
import logging.config
import re
import socket
import time
import urllib.request

from collections import defaultdict
from commentedconfigparser import CommentedConfigParser
from copy import copy
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from subprocess import Popen, PIPE
from urllib.parse import urlparse

import orjson

from watchdog.events import (PatternMatchingEventHandler, DirCreatedEvent, DirDeletedEvent,
                             FileCreatedEvent, FileDeletedEvent, DirModifiedEvent, FileModifiedEvent)
from watchdog.observers import Observer

from lacus.default import AbstractManager, get_config, get_homedir, safe_create_dir
from lacus.default.exceptions import ConfigError

logging.config.dictConfig(get_config('logging'))


@dataclass
class WireProxy:
    name: str

    wireproxy: Path
    config_file: Path
    health_endpoint: str

    loglevel: int = logging.INFO
    logger: Logger = field(init=False)
    process: Popen[bytes] = field(init=False)
    failed_healthcheck: int = 0

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(f'{self.__class__.__name__}:{self.name}')
        self.logger.setLevel(self.loglevel)
        self.process = self._start()
        if not self.is_running():
            raise ConfigError("Unable to start wireproxy.")

    def _start(self) -> Popen[bytes]:
        return Popen([self.wireproxy, '--config', self.config_file, '--info', self.health_endpoint], stdout=PIPE, stderr=PIPE)

    def stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(5)
        except TimeoutError:
            # If the process doesn't terminate, kill it.
            self.logger.info("Unable to terminate, kill.")
            if self.process.poll() is None:
                self.process.kill()

    def restart(self) -> None:
        self.stop()
        self.process = self._start()
        time.sleep(3)

    def is_running(self) -> bool:
        return self.process.poll() is None

    def is_healthy(self) -> bool:
        try:
            with urllib.request.urlopen(f'http://{self.health_endpoint}/readyz', timeout=5) as response:
                if response.status == 200:
                    self.failed_healthcheck = 0
                    return True
        except urllib.error.HTTPError as e:
            self.logger.debug(f"Healthcheck failed: {e.reason}.")
            self.failed_healthcheck += 1
            return False
        except urllib.error.URLError as e:
            self.logger.info(f"Healthcheck endpoint unreachable: {e.reason}.")
            self.failed_healthcheck += 1
            return False
        except TimeoutError:
            # If the endpoint times out, the proxy is in a bad state and we need to restart it.
            self.logger.warning("Healthcheck endpoint timed out, restarting.")
            self.failed_healthcheck += 1
            self.restart()
            return False
        except Exception as e:
            self.failed_healthcheck += 1
            self.logger.error(f"Unexpected error (restarting): {e}")
            self.restart()
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
        self.wireproxy = path_to_wireproxy
        self.configs_dir = configs_dir
        self.proxies_config_path = self.configs_dir / "proxies.json"

        self.wireproxies: dict[str, WireProxy] = {}

        self._init_configs()
        self.launch_all_wireproxies()
        self.logger.debug(f"WireProxyManager initialized with path_to_wireproxy: {path_to_wireproxy}, configs_dir: {configs_dir}")

    def _add_local_port_in_config(self, config_name: str, address: str, port: int | str) -> None:
        """Add port in the dict of local ports currently in use."""
        if address in ['127.0.0.1', 'localhost']:
            p = int(port)
            if p in self.used_local_ports and self.used_local_ports[p] != config_name:
                raise ConfigError(f"[{config_name}] Port {p} already in use by another proxy: {self.used_local_ports[p]}.")
            self.used_local_ports[p] = config_name

    def _port_in_use(self, port: int) -> bool:
        """Check if the port in currently in use on the machine."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            return s.connect_ex(('127.0.0.1', port)) == 0

    def _init_configs(self) -> None:
        """Initialize the proxies.json config file used by Lacus to expose the proxies"""
        # Load the lacus proxy config file
        if not self.proxies_config_path.exists():
            self.proxies = {}
        else:
            with self.proxies_config_path.open('rb') as f:
                self.proxies = orjson.loads(f.read())
        # Add the ports in the config in the used ports
        for name, p in self.proxies.items():
            if p.get('proxy_url'):
                proxy_url = urlparse(p['proxy_url'])
                self._add_local_port_in_config(name, proxy_url.hostname, proxy_url.port)

        # Add the ports in the wireguard config in the used ports
        for config_file in self.configs_dir.glob('*.conf'):
            config_name = config_file.stem
            wg_config = CommentedConfigParser()
            wg_config.read(config_file)
            if socks5_address := wg_config.get('Socks5', 'BindAddress', fallback=None):
                address, _port = socks5_address.split(':')
                self._add_local_port_in_config(config_name, address, _port)

        # Apply config to all wireguard configs
        for config_file in self.configs_dir.glob('*.conf'):
            self.sync_wireguard_proxies(config_file)

    def sync_wireguard_proxies(self, wiregard_config_path: Path) -> bool:
        """Synchronize the wireguard config with the proxies.json config file"""
        config_name = wiregard_config_path.stem
        wg_config_changed = False
        wg_config = CommentedConfigParser()
        wg_config.read(wiregard_config_path)
        proxy_config = copy(self.proxies.get(config_name, {}))
        if proxy_config:
            proxy_config.pop('stopped', None)  # Remove the stopped flag if it exists
        else:
            self.logger.info(f'New proxy: {config_name}')
            # No proxy config found for this wireguard config
            proxy_config = {'description': f"Proxy for {config_name}",
                            'meta': {'provider': 'wireguard'}
                            }
        if proxy_config.get('proxy_url'):
            # Case 1: Proxy config exists in proxy config, force that config in the wireproxy config
            self.logger.debug(f'Setting proxy {config_name} in {config_name}.')
            proxy_url = urlparse(proxy_config['proxy_url'])
            self._add_local_port_in_config(config_name, proxy_url.hostname, proxy_url.port)
            if wg_config.get('Socks5', 'BindAddress', fallback=None) != proxy_url.netloc:
                # If the proxy URL in the wireguard config is None or different, set it to the value from proxies.json
                wg_config['Socks5'] = {'BindAddress': proxy_url.netloc}
                wg_config_changed = True
        else:
            # Case 2: Proxy URL does not exist (create new one)
            # find first unused port in interval
            for port in range(self.min_port, self.max_port):
                if port not in self.used_local_ports and not self._port_in_use(port):
                    # got a free port
                    break
            else:
                raise ConfigError(f"No free port found in range {self.min_port}-{self.max_port}")
            self.logger.debug(f'Initialize new proxy URL for {config_name} on port {port}.')
            proxy_config['proxy_url'] = f"socks5://127.0.0.1:{port}"
            wg_config['Socks5'] = {'BindAddress': f'127.0.0.1:{port}'}
            wg_config_changed = True
            self.used_local_ports[port] = config_name

        # Make sure the DNS is set in the proxies.json config
        if wg_config.get('Interface', 'DNS', fallback=None):
            self.logger.debug(f'Setting DNS resolver for {config_name}.')
            proxy_config['dns_resolver'] = wg_config['Interface']['DNS']

        # Make sure a checkalive is set in the wireguard config
        if not wg_config.get('Interface', 'CheckAlive', fallback=None):
            self.logger.debug(f'Setting CheckAlive for {config_name}.')
            wg_config['Interface']['CheckAlive'] = self.default_checkalive
            wg_config_changed = True

        if wg_config_changed:
            with wiregard_config_path.open('w') as f:
                wg_config.write(f)

        # if the wireguard config was created by protonvpn-wg-config-generate,
        # the config file contains the country code and the city, att it in the meta if possible
        with wiregard_config_path.open('r') as f:
            wg_config_txt = f.read()

        if _cc := re.findall(r".*Country: (\w+)", wg_config_txt):
            proxy_config['meta']['country_code'] = _cc[0]
        if _c := re.findall(r".*City: (\w+)", wg_config_txt):
            proxy_config['meta']['city'] = _c[0]

        if self.proxies.get(config_name) != proxy_config:
            # It's been changed, update and save
            self.proxies[config_name] = proxy_config
            with self.proxies_config_path.open('wb') as f:
                f.write(orjson.dumps(self.proxies, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS))
        return wg_config_changed

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        """A new file was created. Only for new wireguard config files.
        Steps: update proxies.json -> initialize wireproxy config -> launch wireproxy
        """
        filepath = Path(str(event.src_path))
        if isinstance(event, FileCreatedEvent) and filepath.suffix == '.conf':
            if filepath.stem in self.proxies:
                # If something is runinng with that name, stop it.
                self.logger.info(f'A proxy called {filepath.stem} already exists, stopping it.')
                self.stop_wireproxy(filepath.stem)
            else:
                self.logger.info(f'Got new wireguard config file: {filepath.stem}.')
            try:
                self.sync_wireguard_proxies(filepath)
                self.launch_wireproxy(filepath.stem)
            except ConfigError as e:
                self.logger.warning(f"Unable to create the new proxy: {e}")
            except KeyError:
                # Race condition, the file we opened was incomplete/empty
                time.sleep(3)
                if filepath.exists():
                    # Retrigger a modification event
                    filepath.touch(exist_ok=True)

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        """ A file was modified. Only for proxies.json, any change directly made in a wireproxy config file is reverted.
        Steps: update wireproxy config file -> restart wireproxy
        """
        filepath = Path(str(event.src_path))
        if filepath.exists():
            # Race condition, ignore it
            self.logger.info(f'File {filepath} missing, ignoring modified event.')
            return

        if isinstance(event, FileModifiedEvent) and filepath.suffix == '.conf':
            # Modifying the wireproxy config file isn't allowed, but if it happens, we revert it.
            try:
                self.logger.info(f'Wireproxy file modified: {filepath}. Apply the json config')
                if self.sync_wireguard_proxies(filepath):
                    # The wireproxy config has been reverted, stop and restart
                    self.stop_wireproxy(filepath.stem)
                    self.launch_wireproxy(filepath.stem)
            except ConfigError as e:
                self.logger.warning(f"Unable to reapply config: {e}")
            except KeyError:
                # Race condition, the file we opened was incomplete/empty
                time.sleep(3)
                if filepath.exists():
                    # Retrigger a modification event
                    filepath.touch(exist_ok=True)
        elif isinstance(event, FileModifiedEvent) and filepath.name == 'proxies.json':
            with self.proxies_config_path.open('rb') as f:
                proxies = orjson.loads(f.read())
            if proxies == self.proxies:
                # No changes with what we have in memory
                return

            self.logger.info('Proxies file changed.')
            self._init_configs()
            self.launch_all_wireproxies()

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        """ A file was deleted. If it is a wireguard config file, remove it from the proxies.json config file.
        It is it the proxies.json file, reinitialize it from the wireguard config files."""
        filepath = Path(str(event.src_path))
        time.sleep(1)
        if filepath.exists():
            # NOTE: sometimes, modifying the file triggers a delete event
            # But both will be triggered, so the modification will be handled
            # It is safe to ignore.
            self.logger.debug(f'File {filepath} exists, ignoring delete event.')
            return

        if isinstance(event, FileDeletedEvent) and filepath.suffix == '.conf':
            self.logger.info(f'Config file deleted: {filepath}.')
            if self.proxies.pop(filepath.stem, None):
                with self.proxies_config_path.open('wb') as f:
                    f.write(orjson.dumps(self.proxies, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS))
            self.stop_wireproxy(filepath.stem)
        elif isinstance(event, FileDeletedEvent) and filepath.name == 'proxies.json':
            self.logger.info(f'Proxies file deleted: {filepath}, reseting.')
            self._init_configs()
            self.launch_all_wireproxies()

    def remove_proxy(self, name: str) -> None:
        """Remove the proxy entry from proxies.json."""
        if self.proxies.get(name):
            self.proxies[name]['stopped'] = True
            with self.proxies_config_path.open('wb') as f:
                f.write(orjson.dumps(self.proxies, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS))

    # ####  Manage proxy services #### #

    def launch_wireproxy(self, name: str) -> None:
        """Launch wireproxy on a config file, auto-generate a port for healthchecks."""
        if name in self.wireproxies:
            self.logger.info(f"Wireproxy for {name} already exists.")
            if self.wireproxies[name].is_running():
                self.logger.info(f"Wireproxy for {name} is already running.")
                return
            else:
                self.logger.warning(f"Wireproxy for {name} is not running, restarting it.")
                self.wireproxies.pop(name, None)

        config_file = self.configs_dir / f'{name}.conf'
        wg_config = CommentedConfigParser()
        wg_config.read(config_file)

        address, _ = wg_config.get('Socks5', 'BindAddress').split(':')
        for port in range(self.min_port, self.max_port):
            if port not in self.used_local_ports and not self._port_in_use(port):
                self.used_local_ports[port] = f'{config_file.stem}_health'
                break
        else:
            raise Exception(f"[Health] No free port found in range {self.min_port}-{self.max_port}")

        self.wireproxies[config_file.stem] = WireProxy(name=name, wireproxy=self.wireproxy,
                                                       config_file=config_file, health_endpoint=f'{address}:{port}')

    def launch_all_wireproxies(self) -> None:
        """Launch wireproxies on each of the config files in the directory."""
        for config_file in self.configs_dir.glob('*.conf'):
            self.launch_wireproxy(config_file.stem)
        self.logger.info("All wireproxies launched.")

    def stop_wireproxy(self, name: str) -> None:
        """Stop a specific wireproxy, update the proxies.json config file."""
        if name not in self.wireproxies:
            self.logger.debug(f"Wireproxy {name} is not running.")
            return
        self.wireproxies[name].stop()
        self.wireproxies.pop(name, None)
        self.remove_proxy(name)
        self.logger.info(f"Wireproxy for {name} stopped.")

    def stop_all_wireproxies(self) -> None:
        """Stop all the wireproxies."""
        for config_file in self.configs_dir.glob('*.conf'):
            self.stop_wireproxy(config_file.stem)
        self.logger.info("All wireproxies stopped.")

    def clean_used_ports(self) -> None:
        """Once everything is running, make sure the ports are still in use. (they won't if a wireproxy is stopped)"""
        for port in list(self.used_local_ports.keys()):
            if not self._port_in_use(port):
                self.used_local_ports.pop(port)

    def is_wireproxy_runinng(self, name: str) -> bool:
        """Check if the wireproxy is running"""
        if name not in self.wireproxies:
            return False
        return self.wireproxies[name].is_running()

    def is_wireproxy_healthy(self, name: str) -> bool:
        """Check if the wireproxy is healthy"""
        if name not in self.wireproxies:
            self.logger.warning("Unable to check health of wireproxy, {name} is unknown.")
            return False
        if self.wireproxies[name].is_healthy():
            return True
        if self.wireproxies[name].failed_healthcheck > self.max_failed_healthcheck:
            self.logger.warning(f"{name} failed too many healthcheck.")
            return False
        else:
            self.logger.info(f"{name} failed healthcheck, retry later.")
            return True


class WireProxyManager(AbstractManager):

    def __init__(self, loglevel: int | None=None) -> None:
        self.script_name = "wireproxymanager"
        super().__init__(loglevel)
        # it is DEBUG by default, which is very verbose
        watchdog_logger = logging.getLogger('watchdog')
        watchdog_logger.setLevel(logging.WARNING)
        urllib3_logger = logging.getLogger('urllib3')
        urllib3_logger.setLevel(logging.WARNING)

        # The max amount of time a proxy can be restarted before it is archived
        self.max_restarts = 3
        self.restart_counter: dict[str, int] = defaultdict(int)
        safe_create_dir(get_homedir() / 'config' / 'archived_wireproxies')

        path_to_wireproxy = Path(get_config('generic', 'wireproxy_path'))
        if not path_to_wireproxy.exists() or not path_to_wireproxy.is_file():
            raise ConfigError(f"Wireproxy executable not found at {path_to_wireproxy}.")
        self.configs_dir = get_homedir() / 'config'

        self.wpm = WireProxyFSManager(path_to_wireproxy, self.configs_dir, self.logger)

        self.observer = Observer()
        self.observer.schedule(self.wpm, str(self.configs_dir), recursive=False)
        self.observer.start()

        # Just to make sure the proxies have time to start
        time.sleep(5)

    def _to_run_forever(self) -> None:
        # Monitor the status of the proxies
        for config_file in self.configs_dir.glob('*.conf'):
            if self.wpm.is_wireproxy_runinng(config_file.stem):
                self.logger.debug(f'{config_file.stem} is running.')
                if self.wpm.is_wireproxy_healthy(config_file.stem):
                    self.logger.debug(f'{config_file.stem} is healthy.')
                else:
                    self.wpm.stop_wireproxy(config_file.stem)
            else:
                if self.restart_counter[config_file.stem] >= self.max_restarts:
                    self.logger.warning(f'{config_file.stem} has been restarted too many times, archiving.')
                    config_file.rename(get_homedir() / 'config' / 'archived_wireproxies' / config_file.name)
                    self.logger.info(f"Wireproxy {config_file.name} archived.")
                    self.restart_counter.pop(config_file.stem, None)
                else:
                    try:
                        self.wpm.sync_wireguard_proxies(config_file)
                        self.wpm.launch_wireproxy(config_file.stem)
                        self.restart_counter[config_file.stem] += 1
                        self.logger.info(f'{config_file.stem} was not running, restart counter: {self.restart_counter[config_file.stem]}')
                    except ConfigError as e:
                        self.logger.warning(f"Unable to (re)start the new proxy: {e}")
                        self.wpm.stop_wireproxy(config_file.stem)
                        self.restart_counter[config_file.stem] += 1

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
