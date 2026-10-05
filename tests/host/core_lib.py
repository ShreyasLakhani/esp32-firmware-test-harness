"""ctypes wrappers for lib/core."""
import ctypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CORE = ROOT / "lib" / "core"


class FrameT(ctypes.Structure):
    _fields_ = [
        ("seq", ctypes.c_uint32),
        ("ms", ctypes.c_uint32),
        ("pot", ctypes.c_uint16),
        ("ax", ctypes.c_int16),
        ("ay", ctypes.c_int16),
        ("az", ctypes.c_int16),
        ("state", ctypes.c_char),
    ]


class SettingsT(ctypes.Structure):
    _fields_ = [("thr", ctypes.c_uint16), ("stuck_ms", ctypes.c_uint32)]


class AlarmT(ctypes.Structure):
    _fields_ = [("latched", ctypes.c_bool)]


class FaultT(ctypes.Structure):
    _fields_ = [
        ("started", ctypes.c_bool),
        ("ref", ctypes.c_uint16),
        ("ref_ms", ctypes.c_uint32),
        ("stuck", ctypes.c_bool),
        ("range", ctypes.c_bool),
    ]


class Core:
    def __init__(self, lib):
        self.lib = lib
        lib.frame_encode.argtypes = [ctypes.POINTER(FrameT), ctypes.c_char_p, ctypes.c_size_t]
        lib.frame_encode.restype = ctypes.c_int
        lib.frame_parse.argtypes = [ctypes.c_char_p, ctypes.POINTER(FrameT)]
        lib.frame_parse.restype = ctypes.c_int
        lib.cmd_exec.argtypes = [ctypes.c_char_p, ctypes.POINTER(SettingsT), ctypes.c_char_p, ctypes.c_size_t]
        lib.cmd_exec.restype = ctypes.c_int
        lib.settings_default.argtypes = [ctypes.POINTER(SettingsT)]
        lib.alarm_update.argtypes = [ctypes.POINTER(AlarmT), ctypes.c_uint16, ctypes.c_uint16]
        lib.alarm_update.restype = ctypes.c_bool
        lib.alarm_ack.argtypes = [ctypes.POINTER(AlarmT), ctypes.c_uint16, ctypes.c_uint16]
        lib.alarm_ack.restype = ctypes.c_int
        lib.fault_reset.argtypes = [ctypes.POINTER(FaultT)]
        lib.fault_update.argtypes = [ctypes.POINTER(FaultT), ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint32]

    def encode(self, f: FrameT):
        buf = ctypes.create_string_buffer(128)
        n = self.lib.frame_encode(ctypes.byref(f), buf, len(buf))
        return None if n < 0 else buf.value.decode("ascii")

    def parse(self, line: bytes):
        f = FrameT()
        rc = self.lib.frame_parse(line, ctypes.byref(f))
        return rc, f

    def cmd(self, line: bytes, settings: SettingsT):
        reply = ctypes.create_string_buffer(64)
        st = self.lib.cmd_exec(line, ctypes.byref(settings), reply, len(reply))
        return st, reply.value.decode("ascii")
