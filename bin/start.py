from subprocess import Popen, run

from lacus.default import get_homedir


def main() -> None:
    """
    Entry point for the program.

    This function starts the backend (redis), website, and capture manager processes.
    It first checks if the necessary environment variables are set by invoking `get_homedir()`.
    Then it starts the backend process using the `run_backend` command.
    After that, it starts the website and capture manager processes using `Popen`.
    """
    # Just fail if the env isn't set.
    get_homedir()

    print("Start backend (redis)...")
    p = run(["run_backend", "--start"])
    p.check_returncode()
    print("done.")

    print("Start website...")
    Popen(["start_website"])
    print("done.")

    print("Start Capture manager...")
    Popen(["capture_manager"])
    print("done.")


if __name__ == "__main__":
    main()
