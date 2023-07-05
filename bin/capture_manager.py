#!/usr/bin/env python3

import asyncio
import logging
import logging.config
import signal
from asyncio import Task
from typing import Optional, Set

from lacus.default import AbstractManager, get_config
from lacus.lacus import Lacus

logging.config.dictConfig(get_config("logging"))


import asyncio
import signal
from typing import List, Optional, Set


class CaptureManager(AbstractManager):
    """
    A manager class for handling captures.

    Args:
        loglevel (Optional[int]): The log level for the manager. Defaults to None.

    Attributes
    ----------
        script_name (str): The name of the script.
        captures (Set[Task]): A set of ongoing capture tasks.
        lacus (Lacus): An instance of the Lacus class for capturing.

    Methods
    -------
        clear_dead_captures: Clears any dead captures from the list of ongoing captures.
        _to_run_forever_async: Runs the manager asynchronously to process new captures.
        _wait_to_finish_async: Waits for ongoing captures to finish.
    """

    def __init__(self, loglevel: Optional[int] = None):
        super().__init__(loglevel)
        self.script_name: str = "capture_manager"
        self.captures: Set[Task] = set()
        self.lacus: Lacus = Lacus()

    async def clear_dead_captures(self) -> None:
        """Clears any dead captures from the list of ongoing captures."""
        ongoing: List[str] = [capture.get_name() for capture in self.captures]
        for expected_uuid in [uuid for uuid, ts in self.lacus.monitoring.get_ongoing_captures()]:
            if expected_uuid not in ongoing:
                self.lacus.core.clear_capture(
                    expected_uuid, "Capture not in the list of tasks, it has been canceled."
                )

    async def _to_run_forever_async(self) -> None:
        """Runs the manager asynchronously to process new captures."""
        await self.clear_dead_captures()
        if self.force_stop:
            return
        max_new_captures: int = get_config("generic", "concurrent_captures") - len(self.captures)
        self.logger.debug(f"{len(self.captures)} ongoing captures.")
        if max_new_captures <= 0:
            self.logger.info(f"Max amount of captures in parallel reached ({len(self.captures)})")
            return
        for capture_task in self.lacus.core.consume_queue(max_new_captures):
            self.captures.add(capture_task)
            capture_task.add_done_callback(self.captures.discard)
        # NOTE: +1 because running this method also counts for one and will
        #       be decremented when it finishes
        self.set_running(len(self.captures) + 1)

    async def _wait_to_finish_async(self) -> None:
        """Waits for ongoing captures to finish."""
        while self.captures:
            self.logger.info(f"Waiting for {len(self.captures)} capture(s) to finish...")
            self.logger.info(
                f'Ongoing captures: {", ".join(capture.get_name() for capture in self.captures)}'
            )
            await asyncio.sleep(5)
            self.set_running(len(self.captures))
        self.logger.info("No more captures")


def main() -> None:
    """Main entry point for the program."""
    p: CaptureManager = CaptureManager()

    loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(p.stop_async()))

    try:
        loop.run_until_complete(p.run_async(sleep_in_sec=1))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
