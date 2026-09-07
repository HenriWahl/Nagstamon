#!/usr/bin/env python3
"""
Verify that no Mach-O binary inside a macOS app bundle requires a newer macOS than the
bundle claims in LSMinimumSystemVersion.

The wheel tags of the dependencies are not trustworthy - pyqt6-qt6 still tags its arm64
wheel macosx_11_0 while the binaries inside require macOS 13. The Python interpreter the
bundle is built with matters just as much: a Homebrew Python built on macOS 26 drags the
whole bundle up to macOS 26. Without this check such a change goes unnoticed until users
on older systems get a dyld error.

Usage: check_deployment_target.py <path to Nagstamon.app>
"""

import plistlib
import subprocess
import sys
from pathlib import Path

# how many offending files to list before summing up the rest
MAX_REPORTED_FILES = 15

# Mach-O and universal binary magic numbers
MACHO_MAGIC = (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe',
               b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca')


# how many components a version is padded to, so that a bundle declaring '13' and a
# binary requiring '13.0.0' are recognized as the same version - a plain tuple comparison
# would consider the shorter one smaller
VERSION_COMPONENTS = 3


def parse_version(text):
    """
        turn a version string into a padded tuple of ints
    """
    version = tuple(int(x) for x in text.split('.'))
    return version + (0,) * (VERSION_COMPONENTS - len(version))


def version_string(version):
    """
        turn a version tuple back into a printable string
    """
    return '.'.join(str(x) for x in version)


def get_minimum_os_version(path):
    """
        return the minimum macOS version a Mach-O file requires as tuple of ints,
        or None if the file carries no version information

        both load commands which can carry it are evaluated: LC_BUILD_VERSION has a
        'minos' field, the older LC_VERSION_MIN_MACOSX a 'version' one - the same field
        name is also used by LC_ID_DYLIB and LC_LOAD_DYLIB for something entirely
        different, so the current load command has to be tracked
    """
    try:
        output = subprocess.run(['otool', '-l', str(path)],
                                capture_output=True,
                                text=True,
                                check=False).stdout
    except OSError:
        return None

    versions = []
    command = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith('cmd '):
            command = stripped.split(None, 1)[1]
        elif (command == 'LC_BUILD_VERSION' and stripped.startswith('minos ')) or \
                (command == 'LC_VERSION_MIN_MACOSX' and stripped.startswith('version ')):
            try:
                versions.append(parse_version(stripped.split()[1]))
            except ValueError:
                pass
    return max(versions) if versions else None


def get_declared_version(bundle):
    """
        return the minimum macOS version the bundle declares in its Info.plist as tuple
        of ints

        the ways this can go wrong end in a message instead of a traceback, because both
        of them are plausible: a shell glob which did not match any staging directory is
        passed on as a literal path, and a bundle might be built without the key
    """
    plist_path = bundle / 'Contents' / 'Info.plist'
    try:
        with plist_path.open('rb') as file:
            plist = plistlib.load(file)
    except OSError as error:
        sys.exit(f'cannot read {plist_path}: {error}')
    except plistlib.InvalidFileException as error:
        sys.exit(f'cannot parse {plist_path}: {error}')

    if 'LSMinimumSystemVersion' not in plist:
        sys.exit(f'{plist_path} does not contain LSMinimumSystemVersion - the bundle does '
                 f'not declare a minimum macOS version at all')

    declared = plist['LSMinimumSystemVersion']
    try:
        return parse_version(str(declared))
    except ValueError:
        sys.exit(f'{plist_path} declares an unusable LSMinimumSystemVersion {declared!r}')


def collect_versions(bundle):
    """
        return a dict of bundle-relative path to required minimum macOS version for every
        Mach-O file inside the given bundle
    """
    versions = dict()
    for path in bundle.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as file:
            if file.read(4) not in MACHO_MAGIC:
                continue
        minimum = get_minimum_os_version(path)
        if minimum:
            versions[path.relative_to(bundle)] = minimum
    return versions


def main():
    if len(sys.argv) != 2:
        sys.exit(f'usage: {sys.argv[0]} <path to Nagstamon.app>')

    bundle = Path(sys.argv[1])
    declared = get_declared_version(bundle)

    print(f'{bundle.name} declares LSMinimumSystemVersion {version_string(declared)}')

    versions = collect_versions(bundle)
    if not versions:
        sys.exit('no Mach-O files with version information found - wrong path?')

    effective = max(versions.values())
    print(f'checked {len(versions)} Mach-O files, '
          f'they need at least macOS {version_string(effective)}')

    too_new = sorted((version, path) for path, version in versions.items() if version > declared)
    if not too_new:
        print('all of them run on the declared minimum macOS version')
        return

    print(f'\n{len(too_new)} of them require a newer macOS than the bundle claims:')
    for version, path in reversed(too_new[-MAX_REPORTED_FILES:]):
        print(f'  {version_string(version)}  {path}')
    if len(too_new) > MAX_REPORTED_FILES:
        print(f'  ... and {len(too_new) - MAX_REPORTED_FILES} more')

    sys.exit(f'\nThe bundle really needs macOS {version_string(effective)}. Either raise '
             f'LSMinimumSystemVersion or build against dependencies - the Python build '
             f'included - which still support macOS {version_string(declared)}.')


if __name__ == '__main__':
    main()
