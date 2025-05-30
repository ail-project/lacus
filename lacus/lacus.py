#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import logging

from datetime import datetime
from typing import Any

from redis import Redis, ConnectionPool
from redis.connection import UnixDomainSocketConnection

from lacuscore import LacusCore, LacusCoreMonitoring

from .default import get_config, get_socket_path, get_homedir


class Lacus():

    def __init__(self) -> None:
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(get_config('generic', 'loglevel'))

        self.redis_pool: ConnectionPool = ConnectionPool(
            connection_class=UnixDomainSocketConnection,
            path=get_socket_path('cache'),
            health_check_interval=10)

        self.redis_pool_decoded: ConnectionPool = ConnectionPool(
            connection_class=UnixDomainSocketConnection,
            path=get_socket_path('cache'),
            decode_responses=True,
            health_check_interval=10)

        self.headed_allowed = get_config('generic', 'allow_headed')

        self.core = LacusCore(self.redis, tor_proxy=get_config('generic', 'tor_proxy'),
                              only_global_lookups=get_config('generic', 'only_global_lookups'),
                              loglevel=get_config('generic', 'loglevel'),
                              max_capture_time=get_config('generic', 'max_capture_time'),
                              expire_results=get_config('generic', 'expire_results'),
                              max_retries=get_config('generic', 'max_retries'),
                              headed_allowed=self.headed_allowed,
                              )

        self.monitoring = LacusCoreMonitoring(self.redis_decode)

        self.global_proxy = {}
        if global_proxy := get_config('generic', 'global_proxy'):
            if global_proxy.get('enable'):
                self.global_proxy = copy.copy(global_proxy)
                self.global_proxy.pop('enable')

        self._proxies_path = get_homedir() / 'config' / 'proxies.json'
        self._proxies: dict[str, Any] = {}
        self._proxies_last_change: float = 0

    @property
    def redis(self) -> Redis:  # type: ignore[type-arg]
        return Redis(connection_pool=self.redis_pool)

    @property
    def redis_decode(self) -> Redis:  # type: ignore[type-arg]
        return Redis(connection_pool=self.redis_pool_decoded)

    def check_redis_up(self) -> bool:
        return self.redis.ping()

    def redis_status(self) -> dict[str, Any]:
        redis_info = self.redis.info()
        return {'total_keys': redis_info['db0']['keys'] if 'db0' in redis_info else 0,
                'current_memory_use': redis_info['used_memory_rss_human'],
                'peak_memory_use': redis_info['used_memory_peak_human']}

    @property
    def is_busy(self) -> bool:
        max_concurrent_captures = get_config('generic', 'concurrent_captures')
        number_ongoing_captures = len(self.monitoring.get_ongoing_captures())
        if max_concurrent_captures <= number_ongoing_captures:
            return True
        # If the ongoing capture list is not full, we need to check if the queue is also very long
        enqueued_captures = len(self.monitoring.get_enqueued_captures())
        return number_ongoing_captures + enqueued_captures >= max_concurrent_captures

    def status(self) -> dict[str, Any]:
        to_return: dict[str, Any] = {}
        to_return['max_concurrent_captures'] = get_config('generic', 'concurrent_captures')
        to_return['max_capture_time'] = get_config('generic', 'max_capture_time')
        ongoing_captures = self.monitoring.get_ongoing_captures()
        to_return['ongoing_captures'] = len(ongoing_captures)
        to_return['captures_time'] = {uuid: (datetime.now() - start_time).total_seconds() for uuid, start_time in ongoing_captures}
        enqueued_captures = self.monitoring.get_enqueued_captures()
        to_return['enqueued_captures'] = len(enqueued_captures)
        return to_return

    def get_proxy_settings(self, name: str) -> dict[str, Any]:
        """
        Get a proxy from the configuration.
        """
        proxy = self.get_proxies()
        if name in proxy:
            return proxy[name]
        return {}

    def get_proxies(self) -> dict[str, Any]:
        """
        Get the pre-configured proxies from the configuration.
        """
        if not self._proxies_path.exists():
            self.logger.info('No proxies configured.')
            return {}
        if self._proxies_path.stat().st_mtime != self._proxies_last_change:
            self._proxies_last_change = self._proxies_path.stat().st_mtime
            try:
                with self._proxies_path.open('r') as f:
                    self._proxies = json.load(f)
            except json.JSONDecodeError:
                self.logger.warning('Proxies file is not valid JSON.')
                self._proxies = {}
            except Exception as e:
                self.logger.warning(f'Error loading proxies file: {e}')
                self._proxies = {}
        return self._proxies
