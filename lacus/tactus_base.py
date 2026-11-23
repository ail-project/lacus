#!/usr/bin/env python3

from redis import Redis

from lacus.default import get_socket_path, get_config, ConfigError

from lacuscore import SessionMetadataStore, StoredSessionRecord


class TactusBase():

    def __init__(self) -> None:
        remote_headed_settings = get_config('generic', 'remote_headed_settings')
        if remote_headed_settings and remote_headed_settings.get('allow_remote_headed'):
            self.tactus_ip = remote_headed_settings.get('tactus_listen_ip')
            self.tactus_port = remote_headed_settings.get('tactus_listen_port')
        else:
            raise ConfigError('Remote headed not configured.')

        self.redis = Redis(unix_socket_path=get_socket_path('cache'))
        self.session_metadata = SessionMetadataStore(self.redis)
        self.lacus_ip = get_config('generic', 'website_listen_ip')
        self.lacus_port = get_config('generic', 'website_listen_port')

    def get_capture_metadata(self, capture_uuid: str) -> StoredSessionRecord | None:
        return self.session_metadata.read(capture_uuid)
