import os
import sys
import time
import hid
from libs.config import Config


USAGE_PAGE = 0x01  # Generic Desktop
USAGE_KEYBOARD = 0x06  # Keyboard

# How often to look for the keyboard again while it is away. hid.enumerate()
# scans sysfs, so calling it on every poll would stall the GUI event loop.
RECONNECT_INTERVAL = 1.0


class KeyboardBLEHID:
    def __init__(self):
        self.config = Config()
        self.hid = None
        self.path = None
        self.current_layer = None
        self._last_reconnect = 0.0

        self.hid = self.find_device()
        if self.hid is None:
            print("\nNo accessible Bluetooth keyboard HID device found.")
            print(
                f"Please ensure your keyboard is connected and configured correctly on the file {self.config._config_file}"
            )
            self.print_help()
            self.print_available_devices()
            sys.exit(1)

    def find_device(self):
        devices = hid.enumerate()
        keyboards = [
            d
            for d in devices
            if d.get("vendor_id") == self.config.vendor_id
            and d.get("product_id") == self.config.product_id
            and d.get("usage_page") == USAGE_PAGE
            and d.get("usage") == USAGE_KEYBOARD
        ]

        for dev in keyboards:
            device = self.try_open(dev)
            if device is not None:
                return device
        return None

    def try_open(self, dev):
        path = dev.get("path", b"")
        if isinstance(path, bytes):
            path = path.decode()
        manufacturer = dev.get("manufacturer_string", "") or ""
        product = dev.get("product_string", "") or ""

        print(f"Found : {manufacturer} {product}")
        print(f"  Path: {path}")
        print(f"  VID:PID = {dev.get('vendor_id'):04x}:{dev.get('product_id'):04x}")
        print(f"  Usage: page={dev.get('usage_page'):04x} usage={dev.get('usage'):04x}")

        try:
            device = hid.Device(path=dev["path"])
            device.nonblocking = True
            self.path = path
            print("  Opened successfully")
            return device
        except Exception as e:
            print(f"  Could not open: {e}")

    def print_help(self):
        print("\n" + "=" * 60)
        print("TROUBLESHOOTING")
        print("=" * 60)

        if sys.platform == "darwin":
            print(
                """
On macOS, Bluetooth HID devices are protected. Try the following:

1. Run as root

2. Grant Input Monitoring permission:
   System Settings > Privacy & Security > Input Monitoring
   Add Terminal.app (or your Python executable)

3. Consider using USB connection instead.
"""
            )
        else:
            print(
                """
On Linux, you may need to:
1. Add udev rules for HID access
2. Run as root (not recommended)
3. Add user to 'input' or 'plugdev' group
"""
            )

    def print_available_devices(self):
        print("\nAll HID devices on system:")
        for d in hid.enumerate():
            usage_page = d.get("usage_page", 0)
            usage = d.get("usage", 0)
            vid = d.get("vendor_id", 0)
            pid = d.get("product_id", 0)
            manufacturer = d.get("manufacturer_string", "") or ""
            product = d.get("product_string", "") or ""
            print(f"  [{vid:04x}:{pid:04x}] {manufacturer} {product}")
            print(f"    page={usage_page:04x} usage={usage:04x}")

    def close_device(self):
        """Drop the handle so the next poll opens the keyboard afresh."""
        if self.hid is not None:
            try:
                self.hid.close()
            except Exception:
                pass
        self.hid = None
        self.path = None

    def reconnect(self):
        """Look for the keyboard again, at most once every RECONNECT_INTERVAL."""
        now = time.monotonic()
        if now - self._last_reconnect < RECONNECT_INTERVAL:
            return None
        self._last_reconnect = now

        self.hid = self.find_device()
        if self.hid is not None:
            # The keyboard may come back on the layer we last recorded. Forget
            # it, so the first report after reconnecting always redraws rather
            # than comparing equal and leaving a stale image on screen.
            self.current_layer = None
            print("Keyboard reconnected.")
        return self.hid

    def notify_changes(self):
        """
        Embedded protocol
        - Byte 0: Report ID (0x01 for keyboard, 0x02 consumer, 0x03 mouse)
        - Byte 1: Modifier keys
        - Byte 2: Reserved/Layer number
        - Bytes 3+: Key codes

        A Bluetooth keyboard that drops its link comes back on a *different*
        /dev/hidraw node, which leaves this handle pointing at a device that no
        longer exists. Reads on it then sit there quietly forever, so watch the
        node itself and re-open when it goes away.
        """
        if self.path is not None and not os.path.exists(self.path):
            print(f"{self.path} is gone, waiting for the keyboard to come back..")
            self.close_device()

        if self.hid is None and self.reconnect() is None:
            return None

        try:
            data = self.hid.read(64, timeout=100)
            if not data or len(data) < 3:
                return None
            report_id = data[0]

            if report_id != 0x01:  # Not a keyboard report
                return None

            layer = data[2]  # Reserved byte contains layer

            if layer != self.current_layer:
                self.current_layer = layer
                print(f"Layer change: {layer}")
                return layer

        except hid.HIDException as e:
            # Never hold on to a handle we could not re-open: the caller polls
            # us again shortly, and reconnect() is what finds the new node.
            print(f"Device disconnected or not accessible ({e}), re-opening..")
            self.close_device()
            return None

        except Exception as e:
            print(f"Error reading Bluetooth HID: {e}")
            return None

    def __del__(self):
        if self.hid:
            print("Closing HID device...")
            self.hid.close()
