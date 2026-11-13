import sys
import logging
import dateutil.parser
from datetime import datetime, timedelta, timezone

def start_logging(log_name, debug_mode):
    logger = logging.getLogger(log_name)
    handler = logging.StreamHandler(sys.stdout)
    if debug_mode is True:
        LOG_LEVEL = logging.DEBUG
        handler.setLevel(logging.DEBUG)
    else:
        LOG_LEVEL = logging.INFO
        handler.setLevel(logging.INFO)
    logger.setLevel(LOG_LEVEL)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
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
