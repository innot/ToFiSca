from flexx import flx


class Spinner(flx.Widget):
    """A simple text input widget that accepts only integers and has two buttons next to it to
    increase/decrease its value by one.

    Similar to a slider, the Spinner has the three properties
    * value: The current spinner value
    * min: the smallest value the spinner can have.
    * max: the largest value the spinner can have.

    Any user input is clamped to the min and max values.

    This widget emits a :meth:'user_value' event after each change of the value by the user.
    """

    value = flx.IntProp(99, doc="""The current spinner value.""")
    min = flx.IntProp(-(2**32-1), settable=True, doc="""The minimum spinner value""")
    max = flx.IntProp(+(2**32-1), settable=True, doc="""The maximum spinner value.""")

    def init(self):
        with flx.HBox():
            self.dec = flx.Button(text="-", minsize=20)
            self.line = flx.LineEdit(placeholder_text="0000", text=lambda: str(self.value))
            self.inc = flx.Button(text="+", minsize=20)
            flx.Widget(flex=0)

    @flx.emitter
    def user_value(self, value):
        """Event emitted when the user changes the spinner value.
        Has ``old_value`` and ``new_value`` attributes."""
        d = {'old_value': self.value, 'new_value': value}
        self.set_value(value)
        return d

    @flx.action
    def set_value(self, value):
        value = min(value, self.max)
        value = max(self.min, value)
        self._mutate_value(value)

    @flx.reaction('line.user_done')
    def do_user_change(self):
        new_value = int(self.line.text)
        if new_value != new_value:  # NaN check - use previous value
            new_value = self.value
        self.user_value(new_value)

    @flx.reaction('dec.pointer_click')
    def do_decrease(self):
        new_value = self.value - 1
        self.user_value(new_value)

    @flx.reaction('inc.pointer_click')
    def do_increase(self):
        new_value = self.value + 1
        self.user_value(new_value)
