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

# colors
EDGE_COLOR = '#00800040'  # Dark green with low transparancy
FILL_COLOR = '#20f020b0'  # Medium green with high transparancy
ACTIVE_EDGE_COLOR = '#00800040'  # same as non-active edge
ACTIVE_FILL_COLOR = '#f0f020c0'  # Light yellow with trnsparancy

TOP = 0
BOTTOM = 1
LEFT = 2
RIGHT = 3


class RegionOfInterestWidget(flx.CanvasWidget):
    """Special widget to set the boundaries of the region of interest.

    This widget extends canvas and has 4 areas that can be dragged to set the top, bottom, left and right
    edges of the ROI.

    When the edges are moved, a ``roi_changed`` event is emitted.

    Normally each edge is moved independently. If the 'Shift' key is held down both the selected
    edge and the opposite edge are moved together.

    This widget emits a :meth:'user_value' event whenever the roi has been changed by the user.

    The region-of-interest can be externally set by the :meth:'change_roi' action.

    The widget has the following properties:

    * active: If 'True' the widget is active. If set to 'False' the widget becomes inactive (no mouse
      events) and transparent.

    * top, bottom, left, right: The current roi edges as float fractions of the total image width resp. height.

    """
    active = flx.BoolProp(True, settable=True, doc="""If true the roi can be changed.""")

    top = flx.FloatProp(0.1, settable=True, doc="""The top edge of the roi.""")
    bottom = flx.FloatProp(0.9, settable=True, doc="""The bottom edge of the roi.""")
    left = flx.FloatProp(0.2, settable=True, doc="""The left edge of the roi.""")
    right = flx.FloatProp(0.9, settable=True, doc="""The right edge of the roi.""")

    _active_edge = flx.LocalProperty(None, settable=True)

    # remember where in the hitbox the pinter hit to avoid jumps
    _mouse_delta_x = 0
    _mouse_delta_y = 0

    def init(self):
        self._ctx = self.node.getContext('2d')

    @flx.reaction('active')
    def do_active(self):
        if self.active:
            self.apply_style("pointer-events: auto;")
        else:
            self.apply_style("pointer-events: none;")

    @flx.reaction('pointer_down')
    def _on_pointer_down(self, *events):
        width, height = self.size

        # scale
        top = self.top * height
        bot = self.bottom * height
        left = self.left * width
        right = self.right * width

        for ev in events:
            x, y = ev.pos

            # check if any drag boxes are hit
            if left <= x <= right:
                if top - 20 <= y <= top:
                    self._set_active_edge(TOP)
                    self._mouse_delta_y = top - y
                elif bot <= y <= bot + 20:
                    self._set_active_edge(BOTTOM)
                    self._mouse_delta_y = bot - y
                else:
                    self._set_active_edge(None)
            elif top <= y <= bot:
                if left - 20 <= x <= left:
                    self._set_active_edge(LEFT)
                    self._mouse_delta_x = left - x
                elif right <= x <= right + 20:
                    self._set_active_edge(RIGHT)
                    self._mouse_delta_x = right - x
                else:
                    self._set_active_edge(None)
            else:
                self._set_active_edge(None)

    @flx.reaction('pointer_up')
    def _on_pointer_up(self):
        self._set_active_edge(None)

    @flx.reaction('pointer_move')
    def _on_pointer_move(self, *events):
        ev = events[-1]
        shift = 'Shift' in ev.modifiers
        active = self._active_edge

        if active is not None:
            widget_width, widget_height = self.size
            # clamp mouse movement to the image
            m_x, m_y = ev.pos
            pos_x = (m_x + self._mouse_delta_x) / self.size[0]
            pos_y = (m_y + self._mouse_delta_y) / self.size[1]

            top = self.top
            bot = self.bottom
            left = self.left
            right = self.right

            width = right - left
            height = bot - top

            def clamp(value, lower, upper):
                return lower if value < lower else upper if value > upper else value

            # check which edge to move (if shift then move opposite edge as well)
            if active == TOP:
                top = clamp(pos_y, 0.01, 0.98)
                if shift:
                    bot = clamp(pos_y + height, 0.02, 0.99)
                top = clamp(top, 0.01, bot - 0.01)

            if active == BOTTOM:
                bot = clamp(pos_y, 0.02, 0.99)
                if shift:
                    top = clamp(pos_y - height, 0.01, 0.98)
                bot = clamp(bot, top + 0.01, 0.99)

            if active == LEFT:
                left = clamp(pos_x, 0.01, 0.98)
                if shift:
                    right = clamp(pos_x + width, 0.02, 0.99)
                left = clamp(left, 0.01, right - 0.01)

            if active == RIGHT:
                right = clamp(pos_x, 0.02, 0.99)
                if shift:
                    left = clamp(pos_x - width, 0.01, 0.98)
                right = clamp(right, left + 0.01, 0.99)

            self.last_pointer = ev.pos
            self.change_roi(top, bot, left, right)  # update properties and start canvas redraw
            self.user_value()  # inform the world about the new roi

    @flx.action
    def change_roi(self, top, bottom, left, right):
        """Action to update all edges to new values.
        """
        self._mutate_top(top)
        self._mutate_bottom(bottom)
        self._mutate_left(left)
        self._mutate_right(right)

    @flx.emitter
    def user_value(self):
        """Event emitted when the user has changed any edge of the region of interest.
        The event has attributes 'top', 'bottom', 'left' and 'right' with a float number
        from 0.01 to 0.99 of the location of the boundary in relation to the whole widget size.
        For convenience the event also has a 'edges' attribute with a tuple of all
        four edges in the order top, bottom, left, right.
        """
        ret = {"top": self.top,
               "bottom": self.bottom,
               "left": self.left,
               "right": self.right,
               "edges": (self.top, self.bottom, self.left, self.right)
               }
        return ret

    @flx.reaction('size', '_active_edge', 'top', 'bottom', 'left', 'right', 'active')
    def update(self):
        """Redraw the widget."""
        # Init
        ctx = self._ctx
        width, height = self.size
        ctx.clearRect(0, 0, width, height)

        # scale
        top = self.top * height
        bot = self.bottom * height
        left = self.left * width
        right = self.right * width

        # edges
        self.set_context(ctx, 0)  # top
        ctx.beginPath()
        ctx.moveTo(0, top)
        ctx.lineTo(width, top)
        ctx.stroke()
        if self.active:
            ctx.fillRect(left, top - 20, right - left, 20)

        self.set_context(ctx, 1)  # bottom
        ctx.beginPath()
        ctx.moveTo(0, bot)
        ctx.lineTo(width, bot)
        ctx.stroke()
        if self.active:
            ctx.fillRect(left, bot, right - left, 20)

        self.set_context(ctx, 2)  # left
        ctx.beginPath()
        ctx.moveTo(left, 0)
        ctx.lineTo(left, height)
        ctx.stroke()
        if self.active:
            ctx.fillRect(left - 20, top, 20, bot - top)

        self.set_context(ctx, 3)  # right
        ctx.beginPath()
        ctx.moveTo(right, 0)
        ctx.lineTo(right, height)
        ctx.stroke()
        if self.active:
            ctx.fillRect(right, top, 20, bot - top)

    def set_context(self, ctx, current_edge: int):
        ctx.lineWidth = 2
        ctx.strokeStyle = EDGE_COLOR
        ctx.fillStyle = FILL_COLOR
        if current_edge == self._active_edge:
            ctx.strokeStyle = ACTIVE_EDGE_COLOR
            ctx.fillStyle = ACTIVE_FILL_COLOR
