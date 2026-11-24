# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

"""
single sign-on cookies from Windows for Entra ID joined devices

Windows provides cookies derived from the Primary Refresh Token (PRT) of the logged-in user via the COM interface
IProofOfPossessionCookieInfoManager, the same way Edge or the Windows Accounts extension for Chrome do.
Sent to login.microsoftonline.com they allow Entra ID to sign in the user silently.
"""

import ctypes
from ctypes import wintypes
import sys

CLSID_PROOF_OF_POSSESSION_COOKIE_INFO_MANAGER = '{A9927F85-A304-4390-8B23-A75F1C668600}'
IID_IPROOF_OF_POSSESSION_COOKIE_INFO_MANAGER = '{CDAECE56-4EDF-43DF-B113-88E4556FA1BB}'
CLSCTX_INPROC_SERVER = 0x1
COINIT_APARTMENTTHREADED = 0x2
RPC_E_CHANGED_MODE = -2147417850


class GUID(ctypes.Structure):
    _fields_ = [('Data1', wintypes.DWORD),
                ('Data2', wintypes.WORD),
                ('Data3', wintypes.WORD),
                ('Data4', ctypes.c_ubyte * 8)]


class ProofOfPossessionCookieInfo(ctypes.Structure):
    _fields_ = [('name', ctypes.c_void_p),
                ('data', ctypes.c_void_p),
                ('flags', wintypes.DWORD),
                ('p3pHeader', ctypes.c_void_p)]


def _guid(text):
    guid = GUID()
    ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(guid))
    return guid


def get_sso_cookies(uri):
    """
    return dict of SSO cookie names and values Windows offers for the given IdP URI
    empty if not on Windows, device not joined or no PRT available
    """
    if sys.platform != 'win32':
        return {}

    ole32 = ctypes.oledll.ole32
    co_task_mem_free = ctypes.windll.ole32.CoTaskMemFree
    co_task_mem_free.argtypes = [ctypes.c_void_p]

    # COM has to be initialized per thread - server threads did not do it yet
    try:
        ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        uninitialize = True
    except OSError as error:
        if error.winerror != RPC_E_CHANGED_MODE:
            return {}
        uninitialize = False

    cookies = {}
    manager = ctypes.c_void_p()
    try:
        ole32.CoCreateInstance(ctypes.byref(_guid(CLSID_PROOF_OF_POSSESSION_COOKIE_INFO_MANAGER)),
                               None,
                               CLSCTX_INPROC_SERVER,
                               ctypes.byref(_guid(IID_IPROOF_OF_POSSESSION_COOKIE_INFO_MANAGER)),
                               ctypes.byref(manager))
        # vtable: QueryInterface, AddRef, Release, GetCookieInfoForUri
        vtable = ctypes.cast(ctypes.cast(manager, ctypes.POINTER(ctypes.c_void_p))[0],
                             ctypes.POINTER(ctypes.c_void_p))
        get_cookie_info_for_uri = ctypes.WINFUNCTYPE(ctypes.HRESULT,
                                                     ctypes.c_void_p,
                                                     wintypes.LPCWSTR,
                                                     ctypes.POINTER(wintypes.DWORD),
                                                     ctypes.POINTER(ctypes.POINTER(ProofOfPossessionCookieInfo)))(vtable[3])
        release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtable[2])

        count = wintypes.DWORD()
        infos = ctypes.POINTER(ProofOfPossessionCookieInfo)()
        try:
            get_cookie_info_for_uri(manager, uri, ctypes.byref(count), ctypes.byref(infos))
            for index in range(count.value):
                info = infos[index]
                name = ctypes.wstring_at(info.name) if info.name else ''
                data = ctypes.wstring_at(info.data) if info.data else ''
                # data comes as 'value; path=/; domain=...; secure; httponly' - only the value is needed
                if name and data:
                    cookies[name] = data.split(';')[0].strip()
                for pointer in (info.name, info.data, info.p3pHeader):
                    if pointer:
                        co_task_mem_free(pointer)
            if infos:
                co_task_mem_free(ctypes.cast(infos, ctypes.c_void_p))
        finally:
            release(manager)
    except OSError:
        cookies = {}
    finally:
        if uninitialize:
            ole32.CoUninitialize()
    return cookies
