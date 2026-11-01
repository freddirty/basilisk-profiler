# SPDX-License-Identifier: GPL-2.0-or-later
"""Minimal HID access through Windows' own hid.dll / setupapi.dll (ctypes, no extra packages).

Mirrors the small part of the hidapi API that core.device uses: ``enumerate(vid, pid)``
and ``device().open_path(path)`` with feature-report I/O. The device is opened with zero
access rights, which Windows allows even for mouse collections owned by the system.
"""
from __future__ import annotations

import ctypes
import re
from ctypes import wintypes

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_hid = ctypes.WinDLL('hid', use_last_error=True)
_setupapi = ctypes.WinDLL('setupapi', use_last_error=True)

_INVALID_HANDLE = wintypes.HANDLE(-1).value
_FILE_SHARE_READ_WRITE = 0x3
_OPEN_EXISTING = 3
_DIGCF_PRESENT = 0x2
_DIGCF_DEVICEINTERFACE = 0x10
_HIDP_STATUS_SUCCESS = 0x00110000


class _GUID(ctypes.Structure):
    _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD), ('Data3', wintypes.WORD),
                ('Data4', ctypes.c_ubyte * 8)]


class _SpDeviceInterfaceData(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('InterfaceClassGuid', _GUID),
                ('Flags', wintypes.DWORD), ('Reserved', ctypes.c_void_p)]


class _HiddAttributes(ctypes.Structure):
    _fields_ = [('Size', wintypes.ULONG), ('VendorID', wintypes.USHORT),
                ('ProductID', wintypes.USHORT), ('VersionNumber', wintypes.USHORT)]


class _HidpCaps(ctypes.Structure):
    _fields_ = [('Usage', wintypes.USHORT), ('UsagePage', wintypes.USHORT),
                ('InputReportByteLength', wintypes.USHORT),
                ('OutputReportByteLength', wintypes.USHORT),
                ('FeatureReportByteLength', wintypes.USHORT),
                ('Reserved', wintypes.USHORT * 17),
                ('rest', wintypes.USHORT * 10)]


_k32.CreateFileW.restype = wintypes.HANDLE
_k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                             wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
_setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(_GUID), wintypes.LPCWSTR,
                                           wintypes.HWND, wintypes.DWORD]
_setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_GUID), wintypes.DWORD,
    ctypes.POINTER(_SpDeviceInterfaceData)]
_setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(_SpDeviceInterfaceData), ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
_setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
for _name in ('HidD_SetFeature', 'HidD_GetFeature'):
    getattr(_hid, _name).argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
_hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(_HiddAttributes)]
_hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
_hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
_hid.HidD_GetProductString.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
_hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(_HidpCaps)]
_hid.HidP_GetCaps.restype = ctypes.c_long


def _hid_guid() -> _GUID:
    guid = _GUID()
    _hid.HidD_GetHidGuid(ctypes.byref(guid))
    return guid


def _interface_paths() -> list[str]:
    guid = _hid_guid()
    info = _setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None,
                                          _DIGCF_PRESENT | _DIGCF_DEVICEINTERFACE)
    if info in (None, _INVALID_HANDLE):
        raise ctypes.WinError(ctypes.get_last_error())
    paths = []
    try:
        index = 0
        while True:
            data = _SpDeviceInterfaceData(cbSize=ctypes.sizeof(_SpDeviceInterfaceData))
            if not _setupapi.SetupDiEnumDeviceInterfaces(info, None, ctypes.byref(guid), index,
                                                         ctypes.byref(data)):
                break
            index += 1
            needed = wintypes.DWORD()
            _setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(data), None, 0,
                                                       ctypes.byref(needed), None)
            buf = ctypes.create_string_buffer(needed.value)
            # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize: 8 on 64-bit, 6 on 32-bit
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = \
                8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if _setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(data), buf,
                                                          needed, None, None):
                paths.append(ctypes.wstring_at(ctypes.addressof(buf) + 4))
    finally:
        _setupapi.SetupDiDestroyDeviceInfoList(info)
    return paths


def _open(path: str) -> int:
    handle = _k32.CreateFileW(path, 0, _FILE_SHARE_READ_WRITE, None, _OPEN_EXISTING, 0, None)
    if handle == _INVALID_HANDLE:
        raise OSError(ctypes.get_last_error(), f'cannot open {path}')
    return handle


def _describe(path: str) -> dict | None:
    try:
        handle = _open(path)
    except OSError:
        return None
    try:
        attrs = _HiddAttributes(Size=ctypes.sizeof(_HiddAttributes))
        if not _hid.HidD_GetAttributes(handle, ctypes.byref(attrs)):
            return None
        caps = _HidpCaps()
        preparsed = ctypes.c_void_p()
        if _hid.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)):
            try:
                if _hid.HidP_GetCaps(preparsed, ctypes.byref(caps)) & 0xFFFFFFFF \
                        != _HIDP_STATUS_SUCCESS:
                    caps = _HidpCaps()
            finally:
                _hid.HidD_FreePreparsedData(preparsed)
        name = ctypes.create_unicode_buffer(128)
        product = name.value if _hid.HidD_GetProductString(handle, name, 256) else ''
    finally:
        _k32.CloseHandle(handle)
    match = re.search(r'&mi_([0-9a-f]{2})', path, re.IGNORECASE)
    return {
        'path': path.encode(), 'vendor_id': attrs.VendorID, 'product_id': attrs.ProductID,
        'product_string': product, 'usage_page': caps.UsagePage, 'usage': caps.Usage,
        'interface_number': int(match.group(1), 16) if match else -1,
    }


def enumerate(vendor_id: int = 0, product_id: int = 0) -> list[dict]:  # noqa: A001 (hidapi name)
    found = []
    for path in _interface_paths():
        info = _describe(path)
        if info is None:
            continue
        if vendor_id and info['vendor_id'] != vendor_id:
            continue
        if product_id and info['product_id'] != product_id:
            continue
        found.append(info)
    return found


class device:  # noqa: N801 (hidapi name)
    def __init__(self):
        self._handle = None

    def open_path(self, path: bytes | str) -> None:
        self._handle = _open(path.decode() if isinstance(path, bytes) else path)

    def send_feature_report(self, data: bytes | list[int]) -> int:
        data = bytes(data)
        buf = ctypes.create_string_buffer(data, len(data))
        if not _hid.HidD_SetFeature(self._handle, buf, len(data)):
            raise OSError(ctypes.get_last_error(), 'HidD_SetFeature failed')
        return len(data)

    def get_feature_report(self, report_id: int, length: int) -> bytes:
        buf = ctypes.create_string_buffer(bytes([report_id]), length)
        if not _hid.HidD_GetFeature(self._handle, buf, length):
            raise OSError(ctypes.get_last_error(), 'HidD_GetFeature failed')
        return buf.raw

    def close(self) -> None:
        if self._handle is not None:
            _k32.CloseHandle(self._handle)
            self._handle = None
