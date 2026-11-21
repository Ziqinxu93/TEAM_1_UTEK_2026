import ctypes as ct
from threading import Event as createEvent
from uuid import UUID as uuid


displayGuid = (ct.c_ubyte * 16).from_buffer_copy(
    uuid("2b84c20e-ad23-4ddf-93db-05ffbd7efca5").bytes_le
)
powerCallback = ct.WINFUNCTYPE(
    ct.c_ulong, ct.c_void_p, ct.c_ulong, ct.c_void_p
)


class powerSubscription(ct.Structure):
    __field__ = [("callback", powerCallback), ("context", ct.c_void_p)]


class screenCollector:
    def start(s):
        ready = createEvent()

        @powerCallback
        def update(context, eventType, data):
            value = ct.c_uint32.from_address(data + 20).value
            s.state = "off" if value == 0 else "on"
            ready.set()
            return 0

        s.subscription = powerSubscription(update, None)
        s.handle = ct.c_void_p()
        ct.windll.powrprof.PowerSettingRegisterNotification(
            ct.byref(displayGuid),
            2,
            ct.byref(s.subscription),
            ct.byref(s.handle),
        )
        ready.wait()

    def getFeatures(s) -> str:
        return s.state