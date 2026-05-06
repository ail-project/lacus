#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import logging
import logging.config
import signal

from aiohttp import web

from lacus.default import AbstractManager, get_config

from website.web.tactus import make_app

logging.config.dictConfig(get_config('logging'))

"""Sidecar proxy for interactive xpra sessions.

This process is intentionally separate from the main Flask API application so
that Lacus remains a control-plane service. It proxies HTTP and WebSocket
traffic from a stable public route to the per-session xpra unix sockets managed
by LacusCore.
"""


class TactusManager(AbstractManager):

    def __init__(self, loglevel: int | None=None) -> None:
        super().__init__(loglevel)
        self.script_name = 'tactus'
        self.runner: web.AppRunner | None = None

        if remote_headed_settings := get_config('generic', 'remote_headed_settings'):
            if remote_headed_settings.get('allow_remote_headed', False):
                self.listen_ip = remote_headed_settings.get('tactus_listen_ip')
                self.listen_port = int(remote_headed_settings.get('tactus_listen_port'))
            else:
                # Just stop
                self.force_stop = True
                return
        else:
            # Not configured at all
            self.force_stop = True
            return

        self.app = make_app()
        self.site: web.BaseSite | None = None

    async def _to_run_forever_async(self) -> None:
        if self.runner is not None:
            return

        self.logger.info('Starting tactus on %s:%s', self.listen_ip, self.listen_port)
        self.runner = web.AppRunner(self.app, access_log=self.logger)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, host=self.listen_ip, port=self.listen_port)
        await self.site.start()

    async def _wait_to_finish_async(self) -> None:
        if self.runner is None:
            self.logger.info('No runner, nothing to wait for.')
            return

        try:
            await self.runner.cleanup()
        except Exception as e:
            self.logger.warning(f'Unable to clean runner: {e}')


def main() -> None:
    p = TactusManager()

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(p.stop_async()))

    try:
        loop.run_until_complete(p.run_async(sleep_in_sec=1))
    finally:
        loop.close()


if __name__ == '__main__':
    if remote_headed_settings := get_config('generic', 'remote_headed_settings'):
        if not remote_headed_settings.get('allow_remote_headed'):
            print('Remote headfull captures disabled, not starting tactus.')
        else:
            main()
    else:
        # Not configured
        print('Remote headfull captures disabled, not starting tactus.')
