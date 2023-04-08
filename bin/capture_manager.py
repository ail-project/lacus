#!/usr/bin/env python3

import asyncio
import logging
import logging.config
import signal

from asyncio import Task
from typing import Optional, Set


from lacus.default import AbstractManager, get_config
from lacus.lacus import Lacus

logging.config.dictConfig(get_config('logging'))


class CaptureManager(AbstractManager):

    def __init__(self, loglevel: Optional[int]=None):
        super().__init__(loglevel)
        self.script_name = 'capture_manager'
        self.captures: Set[Task] = set()
        self.lacus = Lacus()

    async def clear_dead_captures(self):
        ongoing = [capture.get_name() for capture in self.captures]
        for expected_uuid in [uuid for uuid, ts in self.lacus.monitoring.get_ongoing_captures()]:
            if expected_uuid not in ongoing:
                self.lacus.core.clear_capture(expected_uuid, 'Capture not in the list of tasks, it has been canceled.')

    async def _to_run_forever_async(self):
        await self.clear_dead_captures()
        if self.force_stop:
            return
        self.set_running(len(self.captures))
        max_new_captures = get_config('generic', 'concurrent_captures') - len(self.captures)
        self.logger.debug(f'{len(self.captures)} ongoing captures.')
        if max_new_captures <= 0:
            self.logger.info(f'Max amount of captures in parallel reached ({len(self.captures)})')
            return
        for capture_task in self.lacus.core.consume_queue(max_new_captures):
            self.captures.add(capture_task)
            capture_task.add_done_callback(self.captures.discard)

    async def _wait_to_finish_async(self):
        while self.captures:
            self.logger.info(f'Waiting for {len(self.captures)} capture(s) to finish...')
            await asyncio.sleep(5)
            self.set_running(len(self.captures))
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
