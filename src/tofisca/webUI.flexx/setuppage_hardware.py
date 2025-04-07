from flexx import flx

from tofisca import ProjectManager, CamType


class ProjectController(flx.PyComponent):
    stream_size = (640, 480)

    camera_types = flx.ListProp(settable=True)
    camera_type = flx.StringProp(settable=True)

    def init(self):
        self.set_camera_types([(t.name, f"{t.name} - {t.value}") for t in CamType])
        print(self.camera_types)
        self.set_camera_type("HQ")

    @flx.reaction("camera_type")
    def set_cameratype(self, *events) -> None:
        ev = events[-1]
        camtype = ev.new_value
        print(f"Camera type changed to {camtype}")


class SetuppageHardware(flx.Widget):
    CSS = """
     .flx-SetupPageHardware { background-color: #a0a0a0; }
     """

    def init(self):
        with flx.VBox():
            with flx.FormLayout():
                self.cameratype_combo = flx.ComboBox(title='Camera Type:')
                flx.Widget(flex=1)

    @flx.reaction
    def update(self):
        print(f"debug: self.root = {self.root}")
        print(f"debug: self.root.controller = {self.root.controller}")
        self.cameratype_combo.set_options(self.root.controller.camera_types)
        self.cameratype_combo.set_selected_key(self.root.controller._camera_type)

    @flx.reaction("root.controller.camera_type")
    def do_camera_type(self, *events):
        ev = events[-1]
        ct = ev.new_value
        self.cameratype_combo.set_selected_key(ct)

    @flx.reaction("cameratype_combo.user_selected")
    def do_user_camera_type(self, *events):
        ct = self.cameratype_combo.selected_key
        self.root.controller.set_camera_type(ct)


class Test(flx.PyComponent):
    controller = flx.ComponentProp()

    def init(self):
        self._mutate_controller(ProjectController())
        print(f"Test: controller = {self.controller}")
        self.project = ProjectManager.active_project

        self.hardwarewidget = SetuppageHardware()


if __name__ == '__main__':
    project = ProjectManager.create_project("Hardware_settup", tmp=True)

    app = flx.App(Test)

    app.launch('app')
    # app.serve('')

    flx.start()
