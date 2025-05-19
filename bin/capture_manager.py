#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import logging
import logging.config
import signal

from asyncio import Task
from datetime import datetime, timedelta


from lacus.default import AbstractManager, get_config
from lacus.lacus import Lacus

logging.config.dictConfig(get_config('logging'))


class CaptureManager(AbstractManager):

    def __init__(self, loglevel: int | None=None) -> None:
        super().__init__(loglevel)
        self.script_name = 'capture_manager'
        self.captures: set[Task[None]] = set()
        self.lacus = Lacus()

    async def clear_dead_captures(self) -> None:
        ongoing = {capture.get_name(): capture for capture in self.captures}
        max_capture_time = get_config('generic', 'max_capture_time')
        oldest_start_time = datetime.now() - timedelta(seconds=max_capture_time + (max_capture_time / 10))
        for expected_uuid, start_time in self.lacus.monitoring.get_ongoing_captures():
            if expected_uuid not in ongoing.keys():
                self.lacus.core.clear_capture(expected_uuid, 'Capture not in the list of tasks, it has been canceled.')
            elif start_time < oldest_start_time:
                self.logger.warning(f'{expected_uuid} has been running for too long. Started at {start_time}.')
                capture = ongoing[expected_uuid]
                max_cancel = 5
                while not capture.done() and max_cancel > 0:
                    capture.cancel(f'Capture as been running for more than {max_capture_time}s.')
                    try:
                        await capture
                    except asyncio.CancelledError:
                        self.logger.warning(f'{expected_uuid} is canceled now.')
                    finally:
                        max_cancel -= 1
                        if not capture.done():
                            self.logger.error(f'{expected_uuid} is not done after canceling, trying {max_cancel} more times.')
                            await asyncio.sleep(1)

    async def _to_run_forever_async(self) -> None:

        def clear_list_callback(task: Task[None]) -> None:
            self.captures.discard(task)
            self.unset_running()

        await self.clear_dead_captures()
        if self.force_stop:
            return
        max_new_captures = get_config('generic', 'concurrent_captures') - len(self.captures)
        if max_new_captures <= 0:
            if len(self.lacus.monitoring.get_enqueued_captures()) > 0:
                self.logger.debug(f'Max amount of captures in parallel reached ({len(self.captures)})')
            return
        async for capture_task in self.lacus.core.consume_queue(max_new_captures):
            self.captures.add(capture_task)
            self.set_running()
            capture_task.add_done_callback(clear_list_callback)

    async def _wait_to_finish_async(self) -> None:
        while self.captures:
            self.logger.info(f'Waiting for {len(self.captures)} capture(s) to finish...')
            self.logger.info(f'Ongoing captures: {", ".join(capture.get_name() for capture in self.captures)}')
            await asyncio.sleep(5)
        self.logger.info('No more captures')


def main() -> None:
    p = CaptureManager()

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(p.stop_async()))

    try:
        loop.run_until_complete(p.run_async(sleep_in_sec=1))
    finally:
        loop.close()


if __name__ == '__main__':
    main()
