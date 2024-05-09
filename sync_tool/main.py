import asyncio
import os
import signal
import sys
import threading
from types import FrameType
from typing import Optional

import structlog

from sync_tool.logging import configure_logging

from .app import Application

# If uvloop is installed, use it to run async loop
try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:  # pragma: no cover
    pass

# Signals that should be handled by application
if sys.platform != "win32":
    HANDLED_SIGNALS = (
        signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C .
        signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
        signal.SIGHUP,
    )
if sys.platform == "win32":
    # Windows signal 21. Sent by Ctrl+Break.
    HANDLED_SIGNALS = (
        signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
        signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
        signal.SIGBREAK,
    )

# setup loggers
configure_logging()

logger = structlog.getLogger(__name__)


def main() -> None:
    logger.info("Starting... PID: %s", os.getpid())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Prepare application
    app = Application()

    def handle_exit(signal_number: int, frame: Optional[FrameType]) -> None:
        logger.info("Received signal %s. Sending stop signal to application...", signal.Signals(signal_number).name)
        app.stop()

    # Prepare signal handlers
    if threading.current_thread() is not threading.main_thread():
        logger.warning("Cannot install signal handlers from non-main thread")
        return

    try:
        for sig in HANDLED_SIGNALS:
            if sig is not None:
                signal.signal(sig, handle_exit)
        logger.info("Signal handlers installed")
    except NotImplementedError:  # pragma: no cover
        logger.warning("Signals are not supported. Possible on Windows")

    # Start application loop
    main_task = loop.create_task(app.run_forever())

    try:
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        main_task.cancel()
        loop.run_until_complete(main_task)
        main_task.exception()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
