import structlog
from structlog.contextvars import merge_contextvars
from structlog.dev import ConsoleRenderer, set_exc_info


def configure_logging(is_console: bool = False) -> None:
    """
    Configure logging for the application.
    """
    processors = [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        set_exc_info,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
    ]
    if is_console:
        processors.append(ConsoleRenderer())
    if not is_console:
        processors.append(structlog.processors.UnicodeDecoder())
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = structlog.getLogger(__name__)
    logger.info("Logging configured.")
