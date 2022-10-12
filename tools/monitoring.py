#!/usr/bin/env python3

# import json
import os
import sys

from lacus.default import get_socket_path, AbstractManager
from lacuscore import LacusCoreMonitoring
from rich.console import Console
from rich.padding import Padding
from redis import Redis

console = Console(color_system="256")


class Monitoring():

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
    def number_keys(self):
        return self.redis_cache.info('keyspace')['db0']['keys']

    @property
    def memory_use(self):
        return self.redis_cache.info('memory')


if __name__ == '__main__':
    m = Monitoring()
    if not m.backend_status:
        console.print('[bold red]Backend not up, breaking.[/bold red]')
        sys.exit()

    console.print('DB info:')
    console.print(Padding(f'{m.number_keys} keys in the database.', (0, 2)))
    console.print(Padding(f'Current memory use: {m.memory_use["used_memory_rss_human"]}', (0, 2)))
    console.print(Padding(f'Peak memory use: {m.memory_use["used_memory_peak_human"]}', (0, 2)))

    console.print('Services currently running:')
    running = AbstractManager.is_running()
    for service, number in running:
        s = Padding(f'{service} ({int(number)} service(s))', (0, 2))
        console.print(s)

    console.print('Ongoing captures:')
    for uuid, start_time in m.ongoing:
        s = Padding(f'{uuid}: {start_time}', (0, 2))
        console.print(s)
