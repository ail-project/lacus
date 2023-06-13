#!/usr/bin/env python3

import copy
import logging

from redis import Redis, ConnectionPool
from redis.connection import UnixDomainSocketConnection

from lacuscore import LacusCore, LacusCoreMonitoring

from .default import get_config, get_socket_path


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

        self.core = LacusCore(self.redis, tor_proxy=get_config('generic', 'tor_proxy'),
                              only_global_lookups=get_config('generic', 'only_global_lookups'),
                              loglevel=get_config('generic', 'loglevel'),
                              max_capture_time=get_config('generic', 'max_capture_time'))

        self.monitoring = LacusCoreMonitoring(self.redis_decode)

        self.global_proxy = {}
        if global_proxy := get_config('generic', 'global_proxy'):
            if global_proxy.get('enable'):
                self.global_proxy = copy.copy(global_proxy)
                self.global_proxy.pop('enable')

    @property
    def redis(self):
        return Redis(connection_pool=self.redis_pool)

    @property
    def redis_decode(self):
        return Redis(connection_pool=self.redis_pool_decoded)

    def check_redis_up(self):
        return self.redis.ping()
