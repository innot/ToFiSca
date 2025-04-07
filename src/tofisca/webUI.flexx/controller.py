from flexx import flx

from tofisca import ProjectManager, Project, Parameter, FrameLocationException, PerforationNotFoundException


class ProjectController(flx.PyComponent):
    # image size par
    camera_image_size = flx.TupleProp((-1, -1), settable=True, doc="Camera image size")

    # Framelocator par
    perforation_line = flx.IntProp(-1, settable=True, doc="Perforation line.")

    perforation_top = flx.IntProp(-1, settable=True, doc="Top edge of perforation.")
    perforation_bottom = flx.IntProp(-1, settable=True, doc="Bottom edge of perforation.")

    roirect = flx.TupleProp((-1, -1, -1, -1), settable=True,
                            doc="""The target region-of-interest.""")

    referencepoint = flx.TupleProp((-1, -1), settable=True,
                                   doc="""The reference point of the perforation hole detection.""")

    def init(self):
        self.project.attach(self)
        self.set_camera_image_size((self.project.image_width, self.project.image_height))

    @property
    def project(self) -> Project:
        return ProjectManager.active_project

    @flx.reaction('perforation_line')
    def perf_line_changed(self, *events):
        ev = events[-1]
        new_perfline = ev.new_value
        self.project.set_param(Parameter.ROI_PERFORATION_LINE, new_perfline, source=self)

    @flx.reaction('roirect')
    def roi_changed(self, *events):
        """Reaction to RoI changes by the GUI."""
        print("controller received new roi")
        ev = events[-1]
        new_roi = ev.new_value
        self.project.set_param(Parameter.ROI_RECT, new_roi, source=self)

    @flx.emitter
    def new_roi(self, new_roi):
        """Send an event toward the GUI that the RoI has been changed externally."""
        # The GUI does not listen to roirect itself as otherwise
        # any changes done by the GUI would loop back to the gui (over the network)
        # causing lag and sluggish roi movements.
        return {"new_value": new_roi}

    @flx.action
    def autodetect(self):
        print("Controller: autodetect received")
        try:
            self.project.autodetect_roi()
        except FrameLocationException as exc:
            self.autodetect_error(exc)

        print("Controller: autodetect finished")

    @flx.emitter
    def autodetect_error(self, exception: Exception):
        return {"msg": str(exception)}

    @flx.action
    def manualdetect(self, starting_point: tuple):
        print("Controller: manualdetect received")
        try:
            self.project.manualdetect_roi(starting_point)
        except (FrameLocationException, PerforationNotFoundException) as exc:
            self.manualdetect_error(exc)

    @flx.emitter
    def manualdetect_error(self, exception: Exception):
        return {"msg": str(exception)}

    #
    # images
    #

    @flx.action
    def load_image(self):
        self.project.new_image()
        self.image_ready()

    @flx.emitter
    def image_ready(self):
        return {}

    #
    # Observer
    #

    def update(self, event):
        print(f"controller update() received event {event.name} with value {str(event.new_value)}")
        name = event.name
        new_value = event.new_value
        if name == Parameter.CAMERA_IMAGE_SIZE:
            self.set_camera_image_size(new_value)

        elif event.name == Parameter.ROI_PERFORATION_LINE:
            self.set_perforation_line(new_value)
        elif event.name == Parameter.ROI_PERFORATION_TOP:
            self.set_perforation_top(new_value)
        elif event.name == Parameter.ROI_PERFORATION_BOTTOM:
            self.set_perforation_bottom(new_value)
        elif event.name == Parameter.ROI_RECT:
            self.set_roirect(new_value)
            # now inform the gui. The GUI does not listen to roirect itself as otherwise
            # any changes done by the GUI would loop back to the gui (over the network)
            # causing lag and movement stutter.
            self.new_roi(new_value)
        elif event.name == Parameter.ROI_REFERENCEPOINT:
            self.set_referencepoint(new_value)
        else:
            # log unknown parameter
            pass
