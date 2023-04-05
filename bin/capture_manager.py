#!/usr/bin/env python3

import asyncio
import logging
import logging.config
import signal
import time

from asyncio import Task
from typing import Dict, Optional

from redis import Redis

from lacus.default import AbstractManager, get_config, get_socket_path
from lacus.lacus import Lacus

logging.config.dictConfig(get_config('logging'))


class CaptureManager(AbstractManager):

    def __init__(self, loglevel: Optional[int]=None):
        super().__init__(loglevel)
        self.script_name = 'capture_manager'
        self.captures: Dict[Task, float] = {}
        self.redis: Redis = Redis(unix_socket_path=get_socket_path('cache'))
        self.lacus = Lacus()

    async def _capture(self):
        self.set_running()
        await self.lacus.core.consume_queue()
        self.unset_running()

    async def cancel_old_captures(self):
        cancelled_tasks = []
        for task, timestamp in self.captures.items():
            if time.time() - timestamp >= get_config('generic', 'max_capture_time'):
                task.cancel()
                cancelled_tasks.append(task)
                self.logger.warning('A capture has been going for too long, canceling it.')
        if cancelled_tasks:
            await asyncio.gather(*cancelled_tasks, return_exceptions=True)

    async def _to_run_forever_async(self):
        await self.cancel_old_captures()
        if self.force_stop:
            return
        capture = asyncio.create_task(self._capture())
        self.captures[capture] = time.time()
        capture.add_done_callback(self.captures.pop)
        while len(self.captures) >= get_config('generic', 'concurrent_captures'):
            await self.cancel_old_captures()
            await asyncio.sleep(1)

    async def _wait_to_finish(self):
        while self.captures:
            self.logger.info(f'Waiting for {len(self.captures)} capture(s) to finish...')
            await asyncio.sleep(5)
        self.logger.info('No more captures')


def main():
    p = CaptureManager()

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(p.stop_async()))

    try:
        loop.run_until_complete(p.run_async(sleep_in_sec=1))
    finally:
        loop.close()


if __name__ == '__main__':
    main()
