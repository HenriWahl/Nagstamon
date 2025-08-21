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
        string: A time string in human readable format
    """
    time_object = dateutil.parser.parse(timestring)
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
