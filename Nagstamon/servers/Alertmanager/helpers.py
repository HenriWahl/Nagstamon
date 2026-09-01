import sys
import logging
import dateutil.parser
from datetime import datetime, timedelta, timezone

from Nagstamon.config import conf, debug_queue
# both are shared with the Prometheus server and live in the common helpers now,
# re-exported here to keep this module's interface
from Nagstamon.helpers import (detect_from_labels,
                               get_duration)

class DebugQueueHandler(logging.Handler):
    """
    Hands the log records over to the debug queue of Nagstamon so they show up in the
    debug window and the debug file like the output of every other server
    """

    def emit(self, record):
        debug_queue.append(self.format(record))


def debug_mode_filter(record):
    """Lets debug records pass only while the debug mode is switched on

    Evaluating it per record instead of once at import time is what makes switching the
    debug mode while Nagstamon is running work at all.

    Args:
        record (logging.LogRecord): The record about to be emitted

    Returns:
        bool: True if the record should be emitted
    """
    return record.levelno > logging.DEBUG or conf.debug_mode


def start_logging(log_name):
    """Sets up the logger of this module

    Args:
        log_name (str): Name of the logger

    Returns:
        logging.Logger: The ready to use logger
    """
    logger = logging.getLogger(log_name)
    # a second call must not add the handlers again
    if logger.handlers:
        return logger

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    for handler in (logging.StreamHandler(sys.stdout), DebugQueueHandler()):
        handler.setFormatter(formatter)
        handler.addFilter(debug_mode_filter)
        logger.addHandler(handler)

    # the level is decided per record by debug_mode_filter()
    logger.setLevel(logging.DEBUG)
    return logger


def convert_timestring_to_utc(timestring):
    """Converts time string and returns time for timezone UTC in ISO format

    Args:
        timestring (string): A time string

    Returns:
        string: A time string in ISO format
    """
    local_time = datetime.now(timezone(timedelta(0))).astimezone().tzinfo
    parsed_time = dateutil.parser.parse(timestring)
    utc_time = parsed_time.replace(tzinfo=local_time).astimezone(timezone.utc)
    return utc_time.isoformat()


def add_duration_to_timestring(timestring, hours=0, minutes=0):
    """Adds the given amount of time to a time string and returns it as UTC in ISO format

    Args:
        timestring (string): A time string in local time
        hours (int): Hours to add
        minutes (int): Minutes to add

    Returns:
        string: A time string in ISO format
    """
    local_time = datetime.now(timezone(timedelta(0))).astimezone().tzinfo
    parsed_time = dateutil.parser.parse(timestring).replace(tzinfo=local_time)
    end_time = parsed_time + timedelta(hours=int(hours), minutes=int(minutes))
    return end_time.astimezone(timezone.utc).isoformat()


def split_matchers(text, delimiter=","):
    """Splits a filter expression into single matchers

    A simple split() would break matchers whose value contains the delimiter, like
    severity=~"warning,critical", so delimiters inside quotes are ignored.

    Args:
        text (string): The filter expression
        delimiter (string, optional): The delimiter between matchers. Defaults to ",".

    Returns:
        list(str): The single matchers, stripped and without empty ones
    """
    matchers = []
    current = ""
    quote = None
    for character in text:
        if quote:
            current += character
            if character == quote:
                quote = None
        elif character in ('"', "'"):
            quote = character
            current += character
        elif character == delimiter:
            if current.strip():
                matchers.append(current.strip())
            current = ""
        else:
            current += character
    if current.strip():
        matchers.append(current.strip())
    return matchers
