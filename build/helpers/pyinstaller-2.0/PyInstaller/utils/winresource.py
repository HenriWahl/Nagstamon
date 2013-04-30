#!/usr/bin/env python
#
# Copyright (C) 2009, Florian Hoech
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, 5th Floor, Boston, MA 02110-1301, USA

"""
winresource.py

Read and write resources from/to Win32 PE files.

Commandline usage:
winresource.py <dstpath> <srcpath>
Updates or adds resources from file <srcpath> in file <dstpath>.

2009-03 Florian Hoech

"""

import os.path
import pywintypes
import win32api

import PyInstaller.log as logging
logger = logging.getLogger('PyInstaller.build.winresource')

from PyInstaller.compat import set

LOAD_LIBRARY_AS_DATAFILE = 2
ERROR_BAD_EXE_FORMAT = 193
ERROR_RESOURCE_DATA_NOT_FOUND = 1812
ERROR_RESOURCE_TYPE_NOT_FOUND = 1813
ERROR_RESOURCE_NAME_NOT_FOUND = 1814
ERROR_RESOURCE_LANG_NOT_FOUND = 1815


class File(object):

    """ Win32 PE file class. """

    def __init__(self, filename):
        self.filename = filename

    def get_resources(self, types=None, names=None, languages=None):
        """
        Get resources.

        types = a list of resource types to search for (None = all)
        names = a list of resource names to search for (None = all)
        languages = a list of resource languages to search for (None = all)
        Return a dict of the form {type_: {name: {language: data}}} which
        might also be empty if no matching resources were found.

        """
        return GetResources(self.filename, types, names, languages)

    def update_resources(self, data, type_, names=None, languages=None):
        """
        Update or add resource data.

        type_ = resource type to update
        names = a list of resource names to update (None = all)
        languages = a list of resource languages to update (None = all)

        """
        UpdateResources(self.filename, data, type_, names, languages)

    def update_resources_from_datafile(self, srcpath, type_, names=None,
                                       languages=None):
        """
        Update or add resource data from file srcpath.

        type_ = resource type to update
        names = a list of resource names to update (None = all)
        languages = a list of resource languages to update (None = all)

        """
        UpdateResourcesFromDataFile(self.filename, srcpath, type_, names,
                                    languages)

    def update_resources_from_dict(self, res, types=None, names=None,
                                   languages=None):
        """
        Update or add resources from resource dict.

        types = a list of resource types to update (None = all)
        names = a list of resource names to update (None = all)
        languages = a list of resource languages to update (None = all)

        """
        UpdateResourcesFromDict(self.filename, res, types, names,
                                languages)

    def update_resources_from_resfile(self, srcpath, types=None, names=None,
                                      languages=None):
        """
        Update or add resources from dll/exe file srcpath.

        types = a list of resource types to update (None = all)
        names = a list of resource names to update (None = all)
        languages = a list of resource languages to update (None = all)

        """
        UpdateResourcesFromResFile(self.filename, srcpath, types, names,
                                   languages)


def _GetResources(hsrc, types=None, names=None, languages=None):
    """
    Get resources from hsrc.

    types = a list of resource types to search for (None = all)
    names = a list of resource names to search for (None = all)
    languages = a list of resource languages to search for (None = all)
    Return a dict of the form {type_: {name: {language: data}}} which
    might also be empty if no matching resources were found.

    """
    if types: types = set(types)
    if names: names = set(names)
    if languages: languages = set(languages)
    res = {}
    try:
        # logger.debug("Enumerating resource types")
        enum_types = win32api.EnumResourceTypes(hsrc)
        if types and not "*" in types:
            enum_types = filter(lambda type_:
                                type_ in types,
                                enum_types)
        for type_ in enum_types:
            # logger.debug("Enumerating resources of type %s", type_)
            enum_names = win32api.EnumResourceNames(hsrc, type_)
            if names and not "*" in names:
                enum_names = filter(lambda name:
                                    name in names,
                                    enum_names)
            for name in enum_names:
                # logger.debug("Enumerating resources of type %s name %s", type_, name)
                enum_languages = win32api.EnumResourceLanguages(hsrc,
                                                                type_,
                                                                name)
                if languages and not "*" in languages:
                    enum_languages = filter(lambda language:
                                            language in languages,
                                            enum_languages)
                for language in enum_languages:
                    data = win32api.LoadResource(hsrc, type_, name, language)
                    if not type_ in res:
                        res[type_] = {}
                    if not name in res[type_]:
                        res[type_][name] = {}
                    res[type_][name][language] = data
    except pywintypes.error, exception:
        if exception.args[0] in (ERROR_RESOURCE_DATA_NOT_FOUND,
                                 ERROR_RESOURCE_TYPE_NOT_FOUND,
                                 ERROR_RESOURCE_NAME_NOT_FOUND,
                                 ERROR_RESOURCE_LANG_NOT_FOUND):
            # logger.info('%s: %s', exception.args[1:3])
            pass
        else:
            raise exception
    return res


def GetResources(filename, types=None, names=None, languages=None):
    """
    Get resources from dll/exe file.

    types = a list of resource types to search for (None = all)
    names = a list of resource names to search for (None = all)
    languages = a list of resource languages to search for (None = all)
    Return a dict of the form {type_: {name: {language: data}}} which
    might also be empty if no matching resources were found.

    """
    hsrc = win32api.LoadLibraryEx(filename, 0, LOAD_LIBRARY_AS_DATAFILE)
    res = _GetResources(hsrc, types, names, languages)
    win32api.FreeLibrary(hsrc)
    return res


def UpdateResources(dstpath, data, type_, names=None, languages=None):
    """
    Update or add resource data in dll/exe file dstpath.

    type_ = resource type to update
    names = a list of resource names to update (None = all)
    languages = a list of resource languages to update (None = all)

    """
    # look for existing resources
    res = GetResources(dstpath, [type_], names, languages)
    # add type_, names and languages not already present in existing resources
    if not type_ in res and type_ != "*":
        res[type_] = {}
    if names:
        for name in names:
            if not name in res[type_] and name != "*":
                res[type_][name] = []
                if languages:
                    for language in languages:
                        if not language in res[type_][name] and language != "*":
                            res[type_][name].append(language)
    # add resource to destination, overwriting existing resources
    hdst = win32api.BeginUpdateResource(dstpath, 0)
    for type_ in res:
        for name in res[type_]:
            for language in res[type_][name]:
                logger.info("Updating resource type %s name %s language %s",
                            type_, name, language)
                win32api.UpdateResource(hdst, type_, name, data, language)
    win32api.EndUpdateResource(hdst, 0)


def UpdateResourcesFromDataFile(dstpath, srcpath, type_, names=None,
                                languages=None):
    """
    Update or add resource data from file srcpath in dll/exe file dstpath.

    type_ = resource type to update
    names = a list of resource names to update (None = all)
    languages = a list of resource languages to update (None = all)

    """
    src = open(srcpath, "rb")
    data = src.read()
    src.close()
    UpdateResources(dstpath, data, type_, names, languages)


def UpdateResourcesFromDict(dstpath, res, types=None, names=None,
                            languages=None):
    """
    Update or add resources from resource dict in dll/exe file dstpath.

    types = a list of resource types to update (None = all)
    names = a list of resource names to update (None = all)
    languages = a list of resource languages to update (None = all)

    """
    if types: types = set(types)
    if names: names = set(names)
    if langauges: languages = set(languages)
    for type_ in res:
        if not types or type_ in types:
            for name in res[type_]:
                if not names or name in names:
                    for language in res[type_][name]:
                        if not languages or language in languages:
                            UpdateResources(dstpath,
                                            res[type_][name][language],
                                            [type_], [name], [language])


def UpdateResourcesFromResFile(dstpath, srcpath, types=None, names=None,
                               languages=None):
    """
    Update or add resources from dll/exe file srcpath in dll/exe file dstpath.

    types = a list of resource types to update (None = all)
    names = a list of resource names to update (None = all)
    languages = a list of resource languages to update (None = all)

    """
    res = GetResources(srcpath, types, names, languages)
    UpdateResourcesFromDict(dstpath, res)
