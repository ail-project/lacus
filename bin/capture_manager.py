#!/usr/bin/env python3

import asyncio
import logging

from asyncio import Task
from datetime import datetime
from typing import List, Tuple, Set

from redis.asyncio import Redis

from lacus.default import AbstractManager, get_config, get_socket_path


logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO)


class CaptureManager(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.script_name = 'capture_manager'
        self.semaphore = asyncio.BoundedSemaphore(get_config('generic', 'concurrent_captures'))
        self.captures: Set[Task] = set()
        self.redis: Redis = Redis(unix_socket_path=get_socket_path('cache'))

    async def _capture(self, uuid: str):
        self.set_running()
        await self.redis.sadd('ongoing', uuid)
        to_capture = await self.redis.hgetall(uuid)
        print(datetime.now(), to_capture)
        await asyncio.sleep(30)
        print(datetime.now(), to_capture, 'done')
        self.unset_running()

    async def _to_run_forever_async(self):
        value: List[Tuple[bytes, float]] = await self.redis.zpopmax('to_capture')
        if not value or not value[0]:
            return
        uuid: str = value[0][0].decode()
        capture = asyncio.create_task(self._capture(uuid))
        self.captures.add(capture)
        capture.add_done_callback(self.captures.discard)
        while len(self.captures) >= get_config('generic', 'concurrent_captures'):
            await asyncio.sleep(1)


def main():
    p = CaptureManager()
    asyncio.run(p.run_async(sleep_in_sec=1))


if __name__ == '__main__':
    main()
