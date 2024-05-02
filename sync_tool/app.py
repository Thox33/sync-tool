import asyncio

import structlog

from sync_tool.configuration import Configuration, load_configuration

logger = structlog.getLogger(__name__)


class Application:
    """This class is the main application.
    It will load the configuration initialize all adapters, starts a forever running
    loop and finally shut down all adapters.
    """

    _configuration: Configuration
    _should_stop: bool

    def __init__(self) -> None:
        self._configuration = load_configuration()
        self._should_stop = False

    async def run_forever(self) -> None:
        """Initialize all adapters in configuration and start a forever running loop."""

        try:
            logger.info("Starting application...")
            while not self._should_stop:
                await asyncio.sleep(1)
                logger.info("Application is running...")
        except (Exception, asyncio.CancelledError) as err:
            logger.exception("High level unhandled exception or cancellation", exc_info=err)
        finally:
            logger.info("Application shutdown done")

    def stop(self) -> None:
        self._should_stop = True
        logger.info("Stopping application...")
