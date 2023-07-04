import argparse
import os
import time
from pathlib import Path
from subprocess import Popen
from typing import Dict, Optional

from redis import Redis
from redis.exceptions import ConnectionError

from lacus.default import get_homedir, get_socket_path


def check_running(name: str) -> bool:
    """
    Check if a Redis server with the specified name is running.

    Args:
        name: The name of the Redis server.

    Returns
    -------
        A boolean indicating if the Redis server is running.
    """
    socket_path = get_socket_path(name)
    if not os.path.exists(socket_path):
        return False
    try:
        r = Redis(unix_socket_path=socket_path)
        return bool(r.ping())
    except ConnectionError:
        return False


def launch_cache(storage_directory: Optional[Path] = None):
    """
    Launch a Redis cache server.

    Args:
        storage_directory: Optional storage directory for the Redis server.
                            If not provided, the default home directory will be used.
    """
    if not storage_directory:
        storage_directory = get_homedir()
    if not check_running("cache"):
        Popen(["./run_redis.sh"], cwd=(storage_directory / "cache"))


def shutdown_cache(storage_directory: Optional[Path] = None):
    """
    Shutdown the Redis cache server.

    Args:
        storage_directory: Optional storage directory for the Redis server.
                            If not provided, the default home directory will be used.
    """
    if not storage_directory:
        storage_directory = get_homedir()
    r = Redis(unix_socket_path=get_socket_path("cache"))
    r.shutdown(save=True)
    print("Redis cache database shutdown.")


def launch_all():
    """Launch all backend databases."""
    launch_cache()


def check_all(stop: bool = False):
    """
    Check the status of all backend databases.

    Args:
        stop: If True, wait for all databases to stop; if False, wait for all databases to start.
    """
    backends: Dict[str, bool] = {"cache": False}
    while True:
        for db_name in backends:
            try:
                backends[db_name] = check_running(db_name)
            except Exception:
                backends[db_name] = False
        if stop:
            if not any(running for running in backends.values()):
                break
        else:
            if all(running for running in backends.values()):
                break
        for db_name, running in backends.items():
            if not stop and not running:
                print(f"Waiting on {db_name} to start")
            if stop and running:
                print(f"Waiting on {db_name} to stop")
        time.sleep(1)


def stop_all():
    """Stop all backend databases."""
    shutdown_cache()


def main():
    """
    Manage backend databases using command-line arguments.

    Available arguments:
    --start: Start all backend databases.
    --stop: Stop all backend databases.
    --status: Show the status of all backend databases (default behavior).
    """
    parser = argparse.ArgumentParser(description="Manage backend DBs.")
    parser.add_argument("--start", action="store_true", default=False, help="Start all")
    parser.add_argument("--stop", action="store_true", default=False, help="Stop all")
    parser.add_argument("--status", action="store_true", default=True, help="Show status")
    args = parser.parse_args()

    if args.start:
        launch_all()
    if args.stop:
        stop_all()
    if not args.stop and args.status:
        check_all()
