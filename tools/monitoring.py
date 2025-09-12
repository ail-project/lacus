#!/usr/bin/env python3

from __future__ import annotations

import os
import sys

from datetime import datetime
from typing import Any

import orjson

from lacus.default import get_socket_path, AbstractManager
from lacus import Lacus
from rich.console import Console
from rich.padding import Padding

console = Console(color_system="256")


class Monitoring():

    def __init__(self) -> None:
        self.lacus = Lacus()

    @property
    def backend_status(self) -> bool:
        socket_path_cache = get_socket_path('cache')
        backend_up = True
        if not os.path.exists(socket_path_cache):
            console.print(f'Socket path for the [blue]cache[/blue] redis DB [red]does not exists[/red] ({socket_path_cache}).')
            backend_up = False
        if backend_up:
            try:
                if not self.lacus.monitoring.check_redis_up():
                    console.print('Unable to ping the redis cache db.')
                    backend_up = False
            except ConnectionError:
                console.print('Unable to connect to the redis cache db.')
                backend_up = False

        return backend_up

    @property
    def ongoing(self) -> list[tuple[str, datetime]]:
        return self.lacus.monitoring.get_ongoing_captures()

    @property
    def enqueued(self) -> list[tuple[str, float]]:
        return self.lacus.monitoring.get_enqueued_captures()

    def capture_settings(self, uuid: str) -> dict[str, str]:
        return self.lacus.monitoring.get_capture_settings(uuid)

    @property
    def redis_status(self) -> dict[str, Any]:
        return self.lacus.redis_status()

    @property
    def stats(self) -> dict[str, Any]:
        return self.lacus.monitoring.get_stats(cardinality_only=True)


if __name__ == '__main__':
    m = Monitoring()
    if not m.backend_status:
        console.print('[bold red]Backend not up, breaking.[/bold red]')
        sys.exit()

    console.print('Services currently running:')
    running = AbstractManager.is_running()
    for service, number, pids in running:
        s = Padding(f'{service} ({int(number)} service(s)) - PIDs: {", ".join(pids)}', (0, 2))
        console.print(s)

    console.print('DB info:')
    redis_status = m.redis_status
    console.print(Padding(f'{redis_status["total_keys"]} keys in the database.', (0, 2)))
    console.print(Padding(f'Current memory use: {redis_status["current_memory_use"]}', (0, 2)))
    console.print(Padding(f'Peak memory use: {redis_status["peak_memory_use"]}', (0, 2)))

    console.print('Lacus info:')
    if m.lacus.is_busy:
        console.print(Padding('[red]WARNING[/red]: Lacus is busy.', (0, 2)))
    lacus_status = m.lacus.status()
    console.print(Padding(f'{lacus_status["ongoing_captures"]} ongoing captures.', (0, 2)))
    console.print(Padding(f'{lacus_status["enqueued_captures"]} enqueued captures.', (0, 2)))
    console.print(Padding('Configuration settings', (0, 2)))
    console.print(Padding(f'Max concurrent captures: {lacus_status["max_concurrent_captures"]}', (0, 4)))
    console.print(Padding(f'Max capture time: {lacus_status["max_capture_time"]}', (0, 4)))

    if stats := m.stats:
        console.print('Daily stats:')
        if captures := stats.get('captures'):
            console.print(Padding(f'{captures} captures', (0, 2)))
        if retry_success := stats.get('retry_success'):
            console.print(Padding(f'{retry_success} successful retries', (0, 2)))
        if retry_failed := stats.get('retry_failed'):
            console.print(Padding(f'{retry_failed} failed retries', (0, 2)))
        if errors := stats.get('errors'):
            console.print(Padding('Errors:', (0, 2)))
            for error_name, number in errors:
                console.print(Padding(f'{error_name}: {int(number)}', (0, 4)))

    console.print(f'Ongoing captures ({lacus_status["ongoing_captures"]}):')
    for uuid, start_time in m.ongoing:
        s = Padding(f'{uuid}: {start_time} ({lacus_status["captures_time"][uuid]}s)', (0, 2))
        console.print(s)
        settings = m.capture_settings(uuid)
        if settings:
            s = Padding(orjson.dumps(settings, option=orjson.OPT_INDENT_2).decode(), (0, 4))
            console.print(s)

    console.print(f'Enqueued captures ({lacus_status["enqueued_captures"]}):')
    for uuid, priority in m.enqueued:
        s = Padding(f'{uuid}: {priority}', (0, 2))
        console.print(s)
