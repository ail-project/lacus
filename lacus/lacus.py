#!/usr/bin/env python3

import logging

from redis import Redis

from lacuscore import LacusCore, LacusCoreMonitoring

from .default import get_config, get_socket_path


class Lacus():

    def __init__(self) -> None:
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(get_config('generic', 'loglevel'))

        self.redis = Redis(unix_socket_path=get_socket_path('cache'), health_check_interval=30)
        self.redis_decode = Redis(unix_socket_path=get_socket_path('cache'), decode_responses=True, health_check_interval=30)

        self.core = LacusCore(self.redis, tor_proxy=get_config('generic', 'tor_proxy'),
                              only_global_lookups=get_config('generic', 'only_global_lookups'),
                              loglevel=get_config('generic', 'loglevel'),
                              max_capture_time=get_config('generic', 'max_capture_time'))

        self.monitoring = LacusCoreMonitoring(self.redis_decode)

    def check_redis_up(self):
        return self.redis.ping()
