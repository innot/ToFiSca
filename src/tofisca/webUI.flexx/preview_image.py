from flexx import flx

from webUI.preview_handler import PreviewHandler


class PreviewImage(flx.ImageWidget):

    path = flx.StringProp('/preview', settable=True)

    def init(self):
        super().init()
        self._counter = 0

    def get_counter(self):
        self._counter += 1
        return self._counter

    @flx.reaction('size')
    def size_change(self, *events):
        # only call this if the size has increases (shrinking is handled by the browser)
        ev = events[-1]
        old_w, old_h = ev.old_value
        width, height = self.size
        if width > old_w or height > old_h:
            print(f"PreviewImage: new size (w/h): {width} / {height}")
            self.reload()

    @flx.action
    def reload(self):
        print("PreviewImage starting reload")
        self.do_reload()

    async def do_reload(self):
        width, height = self.size
        path = f"{self.path}?width={width}&counter={self.get_counter()}"
        print(f"PreviewImage Setting source to {path}")
        await self.set_source(path)

# use in case this is widget is changed from an image to a canvas
#    async def load(self, path: str):  # this func must be async to be able to use await
#        global window
#        width, height = self.size
#        response = await window.fetch(path)
#        print(response.status)
#        if response.ok:
#            blob = await response.blob()
#            print(blob)
#            object_url = window.URL.createObjectURL(blob)
#            self.set_image(object_url)
#            print(object_url)


class Test(flx.Widget):

    def init(self):
        with flx.VBox(flex=1):
            self.preview = PreviewImage(path='/preview', flex=1)
            self.btn_reload = flx.Button('Reload', flex=0)

    @flx.reaction('btn_reload.pointer_click')
    def do_reload(self, *events):
        self.preview.reload()


if __name__ == '__main__':
    app = flx.App(Test)

    # Get a ref to the tornado.web.Application object#
    tornado_app = flx.current_server().webui_app

    # Add our handler
    tornado_app.add_handlers(r".*", [(r"/preview", PreviewHandler)])

    m = app.launch('app')
    flx.run()
