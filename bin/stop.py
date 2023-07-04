from subprocess import Popen, run

from redis import Redis
from redis.exceptions import ConnectionError

from lacus.default import get_homedir, get_socket_path


def main() -> None:
    """
    Entry point for the program.

    This function shuts down the databases and backend process.

    It first checks if the necessary environment variables are set by invoking `get_homedir()`.
    Then it shuts down the databases by deleting the "shutdown" key using Redis with the specified socket path.
    After that, it stops the backend process using the `run_backend` command.
    If a ConnectionError occurs during the Redis connection, it is caught and ignored.
    """
    get_homedir()

    # Shut down the databases
    p = Popen(["shutdown"])
    p.wait()

    try:
        # Connect to Redis and delete the "shutdown" key
        r = Redis(unix_socket_path=get_socket_path("cache"), db=1)
        r.delete("shutdown")
        print("Shutting down databases...")

        # Stop the backend process
        p_backend = run(["run_backend", "--stop"])
        p_backend.check_returncode()
        print("done.")
    except ConnectionError:
        # Already down, skip the stack trace
        pass


if __name__ == "__main__":
    main()
