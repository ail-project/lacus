import copy
import logging

from lacuscore import LacusCore, LacusCoreMonitoring
from redis import ConnectionPool, Redis
from redis.connection import UnixDomainSocketConnection

from lacus.default import get_config, get_socket_path


class Lacus:
    """A class representing the Lacus object.

    Lacus is used for interacting with LacusCore and LacusCoreMonitoring
    components for caching and monitoring purposes.

    Attributes
    ----------
        logger (Logger): The logger object for logging information.
        redis_pool (ConnectionPool): The connection pool for the Redis cache.
        redis_pool_decoded (ConnectionPool): The connection pool with decoded responses.
        core (LacusCore): The LacusCore object for performing core functionality.
        monitoring (LacusCoreMonitoring): The LacusCoreMonitoring object for monitoring.
        global_proxy (dict): A dictionary representing global proxy configuration.
    """

    def __init__(self) -> None:
        """Initialize the Lacus object."""
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.logger.setLevel(get_config("generic", "loglevel"))

        self.redis_pool: ConnectionPool = ConnectionPool(
            connection_class=UnixDomainSocketConnection,
            path=get_socket_path("cache"),
            health_check_interval=10,
        )

        self.redis_pool_decoded: ConnectionPool = ConnectionPool(
            connection_class=UnixDomainSocketConnection,
            path=get_socket_path("cache"),
            decode_responses=True,
            health_check_interval=10,
        )

        self.core = LacusCore(
            self.redis,
            tor_proxy=get_config("generic", "tor_proxy"),
            only_global_lookups=get_config("generic", "only_global_lookups"),
            loglevel=get_config("generic", "loglevel"),
            max_capture_time=get_config("generic", "max_capture_time"),
        )

        self.monitoring = LacusCoreMonitoring(self.redis_decode)

        self.global_proxy = {}
        if (global_proxy := get_config("generic", "global_proxy")) and global_proxy.get("enable"):
            self.global_proxy = copy.copy(global_proxy)
            self.global_proxy.pop("enable")

    @property
    def redis(self):
        """Redis: The Redis object connected to the cache."""
        return Redis(connection_pool=self.redis_pool)

    @property
    def redis_decode(self):
        """Redis: The Redis object with decoded responses."""
        return Redis(connection_pool=self.redis_pool_decoded)

    def check_redis_up(self):
        """Check if Redis is up and running.

        Returns
        -------
            bool: True if Redis is up, False otherwise.
        """
        return self.redis.ping()
