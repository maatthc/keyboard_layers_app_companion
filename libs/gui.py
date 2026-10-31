import os
import asyncio
from libs.config import Config

os.environ["KIVY_NO_ARGS"] = "1"

from kivy.app import App  # noqa: F401
from kivy.uix.image import Image  # noqa: F401

imageFolder = "./assets/"


class Gui(App):
    def __init__(self, listener, **kwargs):
        super().__init__(**kwargs)
        self.conf = Config()
        self.listener = listener
        self.updateTask = None

    def on_start(self):
        self.updateTask = asyncio.create_task(self.updateLayer())

    def build(self):
        self.title = "Keyboard Layers App companion"
        self.img = Image(source=imageFolder + self.conf.layers[0], allow_stretch=True)
        return self.img

    async def updateLayer(self, dt=None):
        while True:
            try:
                layer = self.listener.notify_changes()
                if layer is not None:
                    if 0 <= layer < len(self.conf.layers):
                        self.img.source = imageFolder + self.conf.layers[layer]
                        print(f"Switched to layer {layer}: {self.conf.layers[layer]}")
                    else:
                        print(f"Ignoring layer {layer}: no image configured for it")
            except Exception as e:
                print(f"Error: {e}")
            # Outside the try: an error must not skip the sleep. Without a
            # yield point here the loop starves the event loop, so the window
            # stops responding and async_run() can never finish - the app
            # hangs on close instead of exiting.
            await asyncio.sleep(0.1)

    def on_stop(self, **kwargs):
        print("App closing..(did you press ESC?)")
        if self.updateTask is not None:
            self.updateTask.cancel()
        super().on_stop(**kwargs)

    async def start(self):
        await super().async_run()
