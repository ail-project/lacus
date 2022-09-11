#!/usr/bin/env python3

import hashlib
import json
import logging

from typing import Literal, Optional, Union, Dict, List, Any
from uuid import uuid4

from redis import Redis

from .default import get_config, get_socket_path

BROWSER = Literal['chromium', 'firefox', 'webkit']


class Lacus():

    def __init__(self, recapture_interval: int=300, concurrent_captures: int=2) -> None:
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(get_config('generic', 'loglevel'))

        self.redis: Redis = Redis(unix_socket_path=get_socket_path('cache'))
        # Filter out the exact same capture from being triggered multiple times in a short period of time
        self.recapture_interval = recapture_interval

    def check_redis_up(self):
        return self.redis.ping()

    def enqueue(self, *, url: Optional[str]=None,
                document_name: Optional[str]=None, document: Optional[str]=None,
                depth: int=0,
                browser: Optional[BROWSER]=None, device_name: Optional[str]=None,
                user_agent: Optional[str]=None,
                proxy: Optional[Union[str, Dict[str, str]]]=None,
                general_timeout_in_sec: Optional[int]=None,
                cookies: Optional[List[Dict[str, Any]]]=None,
                http_credentials: Optional[Dict[str, int]]=None,
                viewport: Optional[Dict[str, int]]=None,
                referer: Optional[str]=None,
                rendered_hostname_only: bool=True,
                force: bool=False,
                priority: int=0
                ) -> str:
        to_enqueue: Dict[str, Optional[Union[bytes, float, int, str, Dict, List]]] = {'depth': depth, 'rendered_hostname_only': rendered_hostname_only}
        if url:
            to_enqueue['url'] = url
        elif document_name and document:
            to_enqueue['document_name'] = document_name
            to_enqueue['document'] = document
        else:
            raise Exception('Needs either a URL or a document_name *and* a document.')
        if browser:
            to_enqueue['browser'] = browser
        if device_name:
            to_enqueue['device_name'] = device_name
        if user_agent:
            to_enqueue['user_agent'] = user_agent
        if proxy:
            to_enqueue['proxy'] = proxy
        if general_timeout_in_sec is not None:  # that would be a terrible idea, but this one could be 0
            to_enqueue['general_timeout_in_sec'] = general_timeout_in_sec
        if cookies:
            to_enqueue['cookies'] = cookies
        if http_credentials:
            to_enqueue['http_credentials'] = http_credentials
        if viewport:
            to_enqueue['viewport'] = viewport
        if referer:
            to_enqueue['referer'] = referer

        if not force:
            hash_query = hashlib.sha512(json.dumps(to_enqueue).encode()).hexdigest()
            if (existing_uuid := self.redis.get(f'query_hash:{hash_query}')):
                return existing_uuid
        perma_uuid = str(uuid4())

        mapping_capture: Dict[str, Union[bytes, float, int, str]] = {}
        for key, value in to_enqueue.items():
            if isinstance(value, bool):
                mapping_capture[key] = 1 if value else 0
            elif isinstance(value, (list, dict)):
                if value:
                    mapping_capture[key] = json.dumps(value)
            elif value is not None:
                mapping_capture[key] = value

        self.redis.set(f'query_hash:{hash_query}', perma_uuid, nx=True, ex=self.recapture_interval)
        self.redis.hset(perma_uuid, mapping=mapping_capture)  # type: ignore
        self.redis.zadd('to_capture', {perma_uuid: priority})
        return perma_uuid
