"""
Generic dylib path manipulation
"""

import re

__all__ = ['dylib_info']

_DYLIB_RE = re.compile(r"""(?x)
(?P<location>^.*)(?:^|/)
(?P<name>
    (?P<shortname>\w+?)
    (?:\.(?P<version>[^._]+))?
    (?:_(?P<suffix>[^._]+))?
    \.dylib$
)
""")

def dylib_info(filename):
    """
    A dylib name can take one of the following four forms:
        Location/NAME.SomeVersion_Suffix.dylib
        Location/NAME.SomeVersion.dylib
        Location/Name_Suffix.dylib
        Location/NAME.dylib

    returns None if not found or a mapping equivalent to:
        dict(
            location='Location',
            name='NAME.SomeVersion_Suffix.dylib',
            shortname='NAME',
            version='SomeVersion',
            suffix='Suffix',
        )

    Note that SomeVersion and Suffix are optional and may be None
    if not present.
    """
    is_dylib = _DYLIB_RE.match(filename)
    if not is_dylib:
        return None
    return is_dylib.groupdict()
