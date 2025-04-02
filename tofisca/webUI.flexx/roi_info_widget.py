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

import math

from flexx import flx

ACTIVE_COLOR = '#0000b0a0'  # Light blue with low transparancy


class ROIInfoWidget(flx.CanvasWidget):
    """Widget to show and some useful par of the roi manager.

    """

    camera_image_size = (1, 1)

    def init(self):
        self._ctx = self.node.getContext('2d')

    @flx.reaction('root.controller.perforation_line', 'root.controller.perforation_top',
                  'root.controller.perforation_bottom', 'root.controller.referencepoint', 'root.controller.roirect',
                  mode='greedy')
    def update(self):
        """Redraw the widget."""
        # Init
        ctx = self._ctx
        canvas_width, canvas_height = self.size
        image_width, image_height = self.root.controller.camera_image_size
        scale_x = canvas_width / image_width
        scale_y = canvas_height / image_height

        ctx.clearRect(0, 0, canvas_width, canvas_height)
        ctx.strokeStyle = ACTIVE_COLOR
        ctx.lineWidth = 1

        #  perforation line
        pl = self.root.controller.perforation_line
        if pl != -1:
            x = pl * scale_x
            ctx.beginPath()
            ctx.moveTo(x, 0)
            ctx.lineTo(x, canvas_height)
            ctx.stroke()

            # top / bottom of perforation
            for value in [self.root.controller.perforation_top, self.root.controller.perforation_bottom]:
                if value != -1:
                    y = value * scale_y
                    ctx.beginPath()
                    ctx.moveTo(0, y)
                    ctx.lineTo(x, y)
                    ctx.stroke()

        # reference point
        rx, ry = self.root.controller.referencepoint
        if rx != -1 and ry != -1:
            px = pl * scale_x
            x = rx * scale_x
            y = ry * scale_y
            ctx.beginPath()
            ctx.moveTo(x, y)
            ctx.lineTo(px, y)
            ctx.stroke()
            ctx.beginPath()
            ctx.arc(x, y, 10, 0, 2 * math.pi)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(x - 10, y)
            ctx.lineTo(x + 10, y)
            ctx.moveTo(x, y - 10)
            ctx.lineTo(x, y + 10)
            ctx.stroke()

            # roi vector
            rx, ry, _, _ = self.root.controller.roirect
            if rx != -1 or ry != -1:
                rx = rx * scale_x
                ry = ry * scale_y
                ctx.beginPath()
                ctx.moveTo(x, y)
                ctx.lineTo(rx, ry)
                ctx.stroke()
