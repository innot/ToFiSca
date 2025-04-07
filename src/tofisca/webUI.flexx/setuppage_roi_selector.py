# This file is part of the ToFiSca application.
#
# Foobar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ToFiSca is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ToFiSca.  If not, see <http://www.gnu.org/licenses/>.


from flexx import flx

from tofisca import ProjectManager
from webUI._roi_widget import RegionOfInterestWidget
from webUI._spinner import Spinner
from webUI.controller import ProjectController
from webUI.preview_handler import PreviewHandler
from webUI.preview_image import PreviewImage
from webUI.roi_info_widget import ROIInfoWidget
from webUI.startpoint_widget import StartPointWidget


class SetupPageROISelector(flx.Widget):
    """Setup widget page to set the region-of-interest par.
    It has an area to show the (scaled) camera image, overlaid with some gui elements to either
    set the starting point of the perforation hole detection algorithm or to set the edges of
    the region-of-interest.

    This Widget has the following properties:

    * image_width, image_height: The real size of the camera image.
    * reference_point: Tuple with the x and y coordinates of the roi reference point
        (middle of the inner edge of the perforation hole). Can only be set externally and is for info only.
    * roi_rect: Tuple with the x,y, width and height of the region-of-interest.
        Can be set externally (e.g. after an auto_locate) or manually by the user (if required to tweak the area)
    * valid: Bool flag, that - if 'True' - indicates that both the starting_point and the roi are valid.
        Used to activate the 'Next' Button

    This Widget listens to the following events

    * 'root.controller.autodetect_error': autodetection has failed.

    * 'root.controller.manualdetect_error': manual detection has failed.

    * 'root.controller.referencepoint': reference point has changed

    * 'root.controller.image_ready': A new image has been taken by the camera and is ready for display.


    """

    CSS = """
    .flx-SetupPageROISelector { background-color: #a0a0a0; }
    """

    image_width = flx.IntProp(2400)
    image_height = flx.IntProp(1800)

    reference_point = flx.TupleProp((-1, -1), settable=True,
                                    doc="""The reference point of the perforation hole detection.""")

    roi_rect = flx.TupleProp((-1, -1, -1, -1), settable=True,
                             doc="""The target region-of-interest.""")

    valid = flx.BoolProp(False, settable=True,
                         doc="""Flag to indicate that both the starting point and the roi are valid.""")

    info = flx.LocalProperty("", settable=True, doc="""Info Label content.""")
    roi_size = flx.LocalProperty((0, 0), settable=True, doc="""Width and height of the ROI.""")

    canvas_width = 800
    canvas_height = 600

    state = True
    roi_active = False

    def init(self):
        with flx.HBox():
            # Preview / Selector elements
            with flx.VBox(flex=1):
                padding = (self.image_height / self.image_width) * 100
                style = f"position:relative; padding-bottom:{padding}%; top:0; left:0;"
                with flx.PinboardLayout(style=style) as self.pinboard:
                    style = "left:0; right:0; top:0; bottom:0;"
                    self.imagecanvas = PreviewImage(style=style)
                    self.infocanvas = ROIInfoWidget(style=style)
                    self.startpointcanvas = StartPointWidget(style=style)
                    self.roicanvas = RegionOfInterestWidget(style=style)
                self.lbl_info = flx.Label(text=lambda: self.info, wrap=True, flex=1)

            # Control elements
            max_x = self.image_width - 10
            max_y = self.image_height - 10
            with flx.VBox(flex=0):
                with flx.VFix():
                    self.btn_autodetect = flx.Button(text="Autodetect")
                    self.btn_manualdetect = flx.Button(text="Locate Perforation")
                    flx.Widget(flex=0, style='border-style: solid;')  # just a line
                    flx.Label(text="Region of Interest")
                with flx.HFix():
                    flx.Widget(flex=1)
                    self.ltop = Spinner(value=10, min=10, max=max_y)
                    flx.Widget(flex=1)
                with flx.HFix():
                    self.lleft = Spinner(value=10, min=10, max=max_x)
                    flx.Label('+', flex=1, style='border-style:solid; width=50px')
                    self.lright = Spinner(value=max_x, min=10, max=max_x)
                with flx.HFix():
                    flx.Widget(flex=1)
                    self.lbot = Spinner(value=max_y, min=10, max=max_y)
                    flx.Widget(flex=1)
                flx.Widget(flex=0, style='border-style: solid;')  # just a line
                with flx.VFix():
                    flx.Label(text=lambda: f"Width: {self.roi_size[0]}")
                    flx.Label(text=lambda: f"Height: {self.roi_size[1]}")
                    flx.Label(text=lambda: f"Aspect ratio: {self.roi_size[0] / self.roi_size[1]:.4f}")
                flx.Widget(flex=0, style='border-style: solid;')  # just a line
                self.btn_reload = flx.Button(text="Take new Image", icon="foobar")
                flx.Widget(flex=1)

    #
    # Autodetect
    #

    @flx.reaction('btn_autodetect.pointer_click')
    def _do_autodetect(self):
        self.set_info("")  # clear the info label
        # Start autodetection via the controller. The results come back via events.
        self.root.controller.autodetect()

        # reactivate the roicanvas (if it was deactivated)
        self.roicanvas.set_active(True)
        self.startpointcanvas.set_active(False)

    @flx.reaction('root.controller.autodetect_error')
    def _autodetect_error(self, *events):
        """React to a failure of the auto_locate algorithm.
        event.msg describes the cause of the message.
        """
        ev = events[-1]
        self._mutate_valid(False)
        self._mutate_info(ev.msg)

    #
    # Manual Detect
    #

    @flx.reaction('btn_manualdetect.pointer_click')
    def _start_manual_detection(self):
        self.roicanvas.set_active(False)
        self.startpointcanvas.set_active(True)

    @flx.reaction('startpointcanvas.point_set')
    def _do_manual_detect(self, *events):
        ev = events[-1]
        sp_x, sp_y = ev.new_value
        point = (sp_x * self.image_width, sp_y * self.image_height)
        self.set_info("")  # clear the info label
        self.root.controller.manualdetect(point)
        self.startpointcanvas.set_active(False)
        self.roicanvas.set_active(True)

    @flx.reaction('root.controller.manualdetect_error')
    def _manualdetect_error(self, *events):
        """Listen for error message from the controller to indicate that the selected starting point is not valid,
         i.e. it is not within a normal perforation hole.
         """
        ev = events[-1]
        self.set_valid(False)
        self.set_info(ev.msg)
        self._start_manual_detection()  # stay in manual detection mode

    #
    # Spinners
    #

    @flx.reaction('ltop.user_value', 'lbot.user_value', 'lleft.user_value', 'lright.user_value')
    def _spinner_change(self):

        top = self.ltop.value
        bottom = self.lbot.value
        left = self.lleft.value
        right = self.lright.value

        self._update_minmax()

        print(f"spinner change to: {top}, {bottom}, {left}, {right}")
        roi = self.edges_2_rect(top, bottom, left, right)
        self.set_roi_rect(roi)

    def _update_minmax(self):
        """Set the min and max values of the spinners so that the edges can not cross each other."""
        min_area = 20  # pixels between edges
        min_edge = 10  # pixels from the image edges

        self.ltop.set_min(min_edge)
        self.ltop.set_max(self.lbot.value - min_area)

        self.lbot.set_min(self.ltop.value + min_area)
        self.lbot.set_max(self.image_height - min_edge)

        self.lleft.set_min(min_edge)
        self.lleft.set_max(self.lright.value - min_area)

        self.lright.set_min(self.lleft.value + min_area)
        self.lright.set_max(self.image_width - min_edge)

    def _update_spinners(self, top, bottom, left, right):
        self.ltop.set_value(top)
        self.lbot.set_value(bottom)
        self.lleft.set_value(left)
        self.lright.set_value(right)
        self._update_minmax()

    #
    # roi changes
    #

    @flx.reaction('roi_rect')
    def do_roi_change(self):
        """React to changes of the ROI property.
        If the ROI is valid, then activate the roi widget, otherwise deactivate it and allow
        for a manual start point selection.
        """
        if -1 in self.roi_rect:
            self._start_manual_detection()
        else:
            x, y, w, h = self.roi_rect
            top = y
            bottom = y + h
            left = x
            right = x + w

            # update the spinners and labels
            self._update_spinners(top, bottom, left, right)
            self.set_roi_size((right - left, bottom - top))
            self.root.controller.set_roirect(self.roi_rect)

            # convert to fractions
            width = self.image_width
            height = self.image_height

            top = top / height
            bottom = bottom / height
            left = left / width
            right = right / width

            # update the canvas
            self.roicanvas.change_roi(top, bottom, left, right)

    @flx.reaction('roicanvas.user_value')
    def _do_canvas_roi_change(self, *events):
        """React to a change of the roi from the user via the roi canvas widget."""
        ev = events[-1]

        # scale the fractions to image pixel values
        top = round(ev.top * self.image_height)
        bottom = round(ev.bottom * self.image_height)
        left = round(ev.left * self.image_width)
        right = round(ev.right * self.image_width)

        roi = self.edges_2_rect(top, bottom, left, right)
        self.set_roi_rect(roi)

    @flx.reaction('root.controller.new_roi')
    def do_controller_roirect(self, *events):
        """React to a change of the roi from the project, e.g. after loading the project."""
        print("controller roi change event detected")
        ev = events[-1]
        self.set_roi_rect(ev.new_value)
        print(f"    roi set to {ev.new_value}")

    #
    # Reload image button
    #
    @flx.reaction('btn_reload.pointer_click')
    def do_reload(self):
        """Tell the controller to take a new camera image.
        The controller will send an 'image_ready' event once the camera picture is
        loaded and ready for display."""
        self.root.controller.load_image()

    @flx.reaction('root.controller.image_ready')
    def do_image_ready(self):
        print("setup roi widget: image ready received")
        self.imagecanvas.do_reload()

    #
    # Valid / invalid stuff
    #

    @flx.reaction('roi_rect')
    def _check_valid(self):
        w = self.image_width
        h = self.image_height

        r_x, r_y, r_w, r_h = self.roi_rect

        if r_x < 0 or r_x >= (w - r_w):
            self.set_valid(False)
        elif r_y < 0 or r_y >= (h - r_h):
            self.set_valid(False)
        elif r_w < 1 or r_w > (w - r_x):
            self.set_valid(False)
        elif r_h < 1 or r_h > (h - r_y):
            self.set_valid(False)
        else:
            self.set_valid(True)

    @flx.reaction('valid')
    def _do_valid(self):
        # todo show some indication on the gui
        pass

    #
    # utils
    #

    def edges_2_rect(self, top, bottom, left, right) -> tuple:
        """Convert roi defined by edges to one defined by position and size."""
        x = left
        y = top
        w = right - left
        h = bottom - top
        return x, y, w, h


#
# test code
#
class PageROISelectorTest(flx.PyComponent):
    controller = flx.ComponentProp()

    def init(self):
        self._mutate_controller(ProjectController())
        self.project = ProjectManager.active_project
        self.project.new_image(debug=True)
        height, width, _ = self.project.current_frame_image.shape

        self.framewidget = SetupPageROISelector(image_width=width, image_height=height)
        self.framewidget.set_roi_rect(self.controller.roirect)


if __name__ == '__main__':
    flx.config.port = 8890
    flx.config.host_whitelist = '192.168.137.105', 'fe80::ddf4:45ba:8a7b:6a1d'
    flx.set_log_level('DEBUG')

    project = ProjectManager.create_project("PageROISelector", tmp=True)

    app = flx.App(PageROISelectorTest)

    # Get a ref to the tornado.web.Application object#
    tornado_app = flx.current_server().webui_app

    # Add Preview handler
    tornado_app.add_handlers(r".*", [(r"/preview", PreviewHandler)])

    # app.launch('app')
    app.serve('tofisca')

    flx.run()
