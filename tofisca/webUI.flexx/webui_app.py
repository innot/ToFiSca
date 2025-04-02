import asyncio

from flexx import flx


class CreateLoadProjectWidget(flx.VBox):

    def init(self) -> None:
        flx.Label(text="Create / Load Project")
        with flx.HBox():
            flx.Label(text="Project Name")
        flx.Widget(flex=1)


class HardwareWidget(flx.VBox):
    def init(self) -> None:
        flx.Label(text="Hardware Setup")


class ProjectSettings(flx.PyComponent):
    project_name = flx.StringProp("No Active Project ", settable=True)


class WebUIMain(flx.PyWidget):
    settings = flx.ComponentProp()

    def init(self):
        # Place for all the project settings
        self._mutate_settings(ProjectSettings())

        with flx.VBox():
            flx.Label(text="ToFiSca")
            with flx.HSplit(flex=1):
                # Navigation Bar
                with flx.VFix(flex=1, style="border:1px solid #777"):
                    flx.Label(text="Global Setup")
                    self.btn_hardware = flx.Button(text="Hardware")
                    flx.Label(text="Project Setup")
                    self.btn_project = flx.Button(text="Create / Load Project")
                    self.btn_preview = flx.Button(text="Adjust Film")
                    self.btn_camera = flx.Button(text="Camera")
                    flx.Widget(flex=2)

                # Content Area
                with flx.StackLayout(flex=4) as self.stack:
                    self.btn_project.w = CreateLoadProjectWidget()
                    self.btn_hardware.w = HardwareWidget()

    @flx.reaction('btn_hardware.pointer_down', 'btn_project.pointer_down')
    def button_pressed(self, *events):
        print(events[-1])
        button = events[-1].source
        self.stack.set_current(button.w)


class WebUIApp:

    async def run(self):
        self._app = flx.App(WebUIMain)
        self._runner = self._app.serve('tofisca')
        server = flx.current_server()
        if not server._running:
            flx.run()

        return


if __name__ == '__main__':
    asyncio.run(WebUIApp().run())
