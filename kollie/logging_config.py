import logging
import os

import structlog


def configure_logger():
    # configures structlog to produce structured logs in remote envs
    # and pretty logs in local environments

    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
    ]

    if os.environ.get("APPLICATION_STAGE", None) == "local":
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]
        logging.basicConfig(level=logging.INFO)
    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        processors=processors,
        cache_logger_on_first_use=True,
    )
