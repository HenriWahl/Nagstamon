import sys
import logging
import dateutil.parser
from datetime import datetime, timedelta, timezone

from Nagstamon.config import conf, debug_queue

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


def get_duration(timestring):
    """
    calculates the duration (delta) from Prometheus' activeAt (ISO8601
    format) until now and returns a human friendly string

    Args:
        timestring (string): An ISO8601 time string

    Returns:
        string: A time string in human readable format, empty if the given time string is
                missing or unparseable - not every Alertmanager implementation delivers
                all timestamps
    """
    if not timestring:
        return ""
    try:
        time_object = dateutil.parser.parse(timestring)
    except (ValueError, OverflowError, TypeError):
        return ""
    duration = datetime.now(timezone.utc) - time_object
    hour = int(duration.seconds / 3600)
    minute = int(duration.seconds % 3600 / 60)
    second = int(duration.seconds % 60)
    if duration.days > 0:
        return "%sd %sh %02dm %02ds" % (duration.days, hour, minute, second)
    if hour > 0:
        return "%sh %02dm %02ds" % (hour, minute, second)
    if minute > 0:
        return "%02dm %02ds" % (minute, second)
    return "%02ds" % (second)


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


def detect_from_labels(labels, config_label_list, default_value="", list_delimiter=","):
    """Returns the name of the label that first matched between `labels` and `config_label_list`.
    If there has not been a match it returns an empty string.

    Args:
        labels (list(str)):  A list of string labels
        config_label_list (str):  A delimiter seperated list - Delimiter can be specified with `list_delimiter`. Default delimiter is ",".
        default_value (str, optional): The value to return if there has not been a match. Defaults to "".
        list_delimiter (str, optional): The delimiter used in the value of `config_label_list`. Defaults to ",".

    Returns:
        str: The matched label name or an empty string if there was no match
    """
    result = default_value
    for each_label in config_label_list.split(list_delimiter):
        if each_label in labels:
            result = labels.get(each_label)
            break
    return result


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
