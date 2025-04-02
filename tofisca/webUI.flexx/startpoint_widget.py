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
from pscript import window

ACTIVE_COLOR = '#00b00080'  # Light green with medium transparency


class StartPointWidget(flx.CanvasWidget):
    """Widget to show and set the starting point for the ROILocator.

    It has two modes:
    * Active mode, where the widget shows a crosshair over the current mouse position until the mouse
      button is clicked.

    * Non-Active mode, where the selected starting point is shown together with the reference point and a
      vector to the ROI (if set)

    The set mode is activated externally (by :meth:'set_active(True)') and is active until the user clicks
    somewhere in the widget.

    """

    active = flx.BoolProp(False, settable=True)

    mouse_inside = False  # Flag to indicate if the mouse cursor is inside the widget

    pointer_pos = (0, 0)  # position of the mouse pointer

    def init(self):
        self._ctx = self.node.getContext('2d')

    def do_mouse_over(self, e):
        if e.target == self.node:
            self.mouse_inside = True
        else:
            self.mouse_inside = False

        self.update()

    @flx.reaction('pointer_move')
    def do_pointer_move(self, *events):
        ev = events[-1]
        self.pointer_pos = ev.pos
        self.update()

    @flx.reaction('pointer_down')
    def _on_pointer_down(self, *events):
        ev = events[-1]
        if self.active:
            if ev.button == 1:  # left click - set new starting point
                width, height = self.size
                x, y = ev.pos
                point = (x / width, y / height)

                # emit a seperate event to avoid loops when changing the start point
                self.point_set(point)

            self.set_active(False)

    @flx.emitter
    def point_set(self, point: tuple):
        """Emitted when a new starting point has been selected.
        """
        return {"old_value": self.start_point,
                "new_value": point}

    @flx.reaction('active')
    def do_active(self):
        if self.active:
            self.set_capture_mouse(2)
            window.document.addEventListener("mouseover", self.do_mouse_over, True)
        else:
            self.set_capture_mouse(1)
            window.document.removeEventListener("mouseover", self.do_mouse_over, True)

    @flx.reaction('size', 'active')
    def update(self):
        """Redraw the widget."""
        # Init
        ctx = self._ctx
        width, height = self.size
        ctx.clearRect(0, 0, width, height)
        ctx.strokeStyle = ACTIVE_COLOR

        # crosshair
        if self.active:
            if self.mouse_inside:
                x, y = self.pointer_pos
                ctx.lineWidth = 3
                ctx.beginPath()
                ctx.moveTo(x, 0)
                ctx.lineTo(x, height)
                ctx.stroke()

                ctx.beginPath()
                ctx.moveTo(0, y)
                ctx.lineTo(width, y)
                ctx.stroke()
