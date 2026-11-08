"""Visible data failures instead of plausible zero-valued results."""

import logging

logger = logging.getLogger("calliope_dashboard.data")


class DataUnavailable(ValueError):
    pass


def fail(message, error=None):
    logger.error(message, exc_info=error is not None)
    raise DataUnavailable(message) from error
