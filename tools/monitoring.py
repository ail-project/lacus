#!/usr/bin/env python3

import json
import os
import sys

from lacuscore import LacusCoreMonitoring
from redis import Redis
from rich.console import Console
from rich.padding import Padding

from lacus.default import AbstractManager, get_socket_path

console = Console(color_system="256")


class Monitoring:

    def __init__(self):
        self.redis_cache: Redis = Redis(unix_socket_path=get_socket_path('cache'), decode_responses=True)

        self.lacus_monit = LacusCoreMonitoring(self.redis_cache)

    @property
    def backend_status(self):
        socket_path_cache = get_socket_path('cache')
        backend_up = True
        if not os.path.exists(socket_path_cache):
            console.print(f'Socket path for the [blue]cache[/blue] redis DB [red]does not exists[/red] ({socket_path_cache}).')
            backend_up = False
        if backend_up:
            try:
                if not self.lacus_monit.check_redis_up():
                    console.print('Unable to ping the redis cache db.')
                    backend_up = False
            except ConnectionError:
                console.print('Unable to connect to the redis cache db.')
                backend_up = False

        return backend_up

    @property
    def ongoing(self):
        return self.lacus_monit.get_ongoing_captures()

    @property
    def enqueued(self):
        return self.lacus_monit.get_enqueued_captures()

    def capture_settings(self, uuid: str):
        return self.lacus_monit.get_capture_settings(uuid)

    @property
    def number_keys(self):
        return self.redis_cache.info('keyspace')['db0']['keys']

    @property
    def memory_use(self):
        return self.redis_cache.info('memory')

    @property
    def stats(self):
        return self.lacus_monit.get_stats()


if __name__ == '__main__':
    m = Monitoring()
    if not m.backend_status:
        console.print('[bold red]Backend not up, breaking.[/bold red]')
        sys.exit()

    console.print('Services currently running:')
    running = AbstractManager.is_running()
    for service, number in running:
        s = Padding(f'{service} ({int(number)} service(s))', (0, 2))
        console.print(s)

    console.print('DB info:')
    console.print(Padding(f'{m.number_keys} keys in the database.', (0, 2)))
    console.print(Padding(f'Current memory use: {m.memory_use["used_memory_rss_human"]}', (0, 2)))
    console.print(Padding(f'Peak memory use: {m.memory_use["used_memory_peak_human"]}', (0, 2)))

    if stats := m.stats:
        console.print('Daily stats:')
        if captures := stats.get('captures'):
            console.print(Padding(f'{len(captures)} captures', (0, 2)))
        if retry_success := stats.get('retry_success'):
            console.print(Padding(f'{len(retry_success)} successful retries', (0, 2)))
        if retry_failed := stats.get('retry_failed'):
            console.print(Padding(f'{len(retry_failed)} failed retries', (0, 2)))
        if errors := stats.get('errors'):
            console.print(Padding('Errors:', (0, 2)))
            for error_name, number in errors:
                console.print(Padding(f'{error_name}: {int(number)}', (0, 4)))

    console.print('Ongoing captures:')
    for uuid, start_time in m.ongoing:
        s = Padding(f'{uuid}: {start_time}', (0, 2))
        console.print(s)
        settings = m.capture_settings(uuid)
        if settings:
            s = Padding(json.dumps(settings, indent=2), (0, 4))
            console.print(s)

    console.print('Enqueued captures:')
    for uuid, priority in m.enqueued:
        s = Padding(f'{uuid}: {priority}', (0, 2))
        console.print(s)
