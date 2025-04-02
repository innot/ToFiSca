from flexx import flx

from tofisca import ProjectManager, Project
from webUI.livestream_handler import LiveStreamHandler


class ProjectController(flx.PyComponent):
    stream_size = (640, 480)

    def init(self):
        pass

    @flx.action
    def set_stream_size(self, size: tuple) -> None:
        self.stream_size = size

    @flx.action
    def start_streaming(self) -> None:
        project = ProjectManager.active_project
        project.camera_manager.start_streaming(self.stream_size)
        self.streaming_started(True)

    @flx.action
    def stop_streaming(self):
        project = ProjectManager.active_project
        project.camera_manager.stop_streaming()
        self.streaming_started(False)

    @flx.emitter
    def streaming_started(self, state: bool):
        return {"new_value": state}


class VideoPreview(flx.Widget):
    CSS = """
    .flx-VideoPreview { background-color: #a0a0a0; }
    """

    def init(self):
        with flx.VBox():
            with flx.HBox(flex=3):
                self.preimg = flx.ImageWidget()
                self.preimg.set_minsize((600, 480))
            with flx.HBox(flex=1):
                self.start_btn = flx.Button(text="Start")
                self.stop_btn = flx.Button(text="Stop")
            flx.Widget(flex=2)

    @flx.reaction('start_btn.pointer_click')
    def handle_start(self, *events):
        print("VideoPreview: start clicked")
        # self.root.controller.set_stream_size(self.preimg.size)
        # self.root.controller.start_streaming()

    @flx.reaction('stop_btn.pointer_click')
    def handle_stop(self, *events):
        print("VideoPreview: stop clicked")

    #        self.preimg.set_source("/none")
    # self.root.controller.stop_streaming()

    @flx.reaction('size')
    def handle_resize(self, *events):
        width, height = self.preimg.size
        if width != 0 and height != 0:  # skip any calls while the widget has not been given a size
            self.preimg.set_source(f"/live?width={width}&height={height}")

    # @flx.reaction('root.controller.streaming_started')
    # def handle_streaming_started(self):
    #    self.preimg.set_source("/live")


class Test(flx.PyComponent):
    controller = flx.ComponentProp()

    def init(self):
        self._mutate_controller(ProjectController())
        self.videowidget = VideoPreview()


if __name__ == '__main__':
    project = ProjectManager.create_project("Video_Preview", tmp=True)

    #    flx.config.port = 8890
    #    flx.config.host_whitelist = '192.168.137.1:8890'
    #    flx.set_log_level('DEBUG')
    app = flx.App(Test)

    # Get a ref to the tornado.web.Application object#
    tornado_app = flx.current_server().webui_app

    # Add Preview handler
    tornado_app.add_handlers(r".*", [(r"/live", LiveStreamHandler)])

    app.launch('app')
    # app.serve('')

    flx.start()
