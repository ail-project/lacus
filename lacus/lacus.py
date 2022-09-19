#!/usr/bin/env python3

import logging

from redis import Redis

from lacuscore import LacusCore

from .default import get_config, get_socket_path


class Lacus():

    def __init__(self) -> None:
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(get_config('generic', 'loglevel'))

        self.redis = Redis(unix_socket_path=get_socket_path('cache'))

        self.core = LacusCore(self.redis, get_config('generic', 'tor_proxy'),
                              get_config('generic', 'only_global_lookups'))

    def check_redis_up(self):
        return self.redis.ping()
