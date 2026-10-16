import datetime

import arrow


def humanise_date_filter(date: datetime.datetime) -> str:
    """
    Converts a date to a human-readable age.

    Returns:
        str: The human-readable age.
             e.g.
                past: "3 days ago", "2 hours ago", "1 minute ago", "just now"
                future: "3 days", "2 hours", "1 minute", "now"

    """
    try:
        return arrow.get(date).humanize()
    except (AttributeError, TypeError, ValueError):
        # mypy isn't able to enforce type checking on this function when it's
        # called from a Jinja template, so we handle that here
        return "unknown"
