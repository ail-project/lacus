import time

from lacus.default import AbstractManager


def main() -> None:
    """
    Entry point for the program.

    This function checks if the AbstractManager is running and waits for it to shut down.
    It prints the status of the AbstractManager every 5 seconds until it is no longer running or encounters an error.
    """
    AbstractManager.force_shutdown()
    time.sleep(5)

    while True:
        try:
            running = AbstractManager.is_running()
        except FileNotFoundError:
            print("Redis is already down.")
            break

        if not running:
            break

        print(running)
        time.sleep(5)


if __name__ == "__main__":
    main()
