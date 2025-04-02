#  This file is part of the ToFiSca application.
#
#  ToFiSca is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ToFiSca is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ToFiSca.  If not, see <http://www.gnu.org/licenses/>.
#
#  Copyright (c) 2025 by Thomas Holland, thomas@innot.de
#
#!/usr/bin/python3
import threading


class Controls:

    @staticmethod
    def _framerates_to_durations_(framerates: tuple) -> tuple[int,int]:
        if not isinstance(framerates, (tuple, list)):
            framerates = (framerates, framerates)
        return int(1000000 / framerates[1]), int(1000000 / framerates[0])

    @staticmethod
    def _durations_to_framerates_(durations):
        if durations[0] == durations[1]:
            return 1000000 / durations[0]
        return 1000000 / durations[1], 1000000 / durations[0]

    _VIRTUAL_FIELDS_MAP_ = {"FrameRate": ("FrameDurationLimits", _framerates_to_durations_, _durations_to_framerates_)}

    def __init__(self, picam2, controls=None):
        if not controls:
            controls = {}

        self._picam2 = picam2
        self._controls = []
        self._lock = threading.Lock()
        self.set_controls(controls)

    def __setattr__(self, name, value):
        if not name.startswith('_'):
            if name in Controls._VIRTUAL_FIELDS_MAP_:
                real_field = Controls._VIRTUAL_FIELDS_MAP_[name]
                name = real_field[0]
                value = real_field[1](value)
            if name not in self._picam2.camera_ctrl_info.keys():
                raise RuntimeError(f"Control {name} is not advertised by libcamera")
            self._controls.append(name)
        self.__dict__[name] = value

    def __getattribute__(self, name):
        if name in Controls._VIRTUAL_FIELDS_MAP_:
            real_field = Controls._VIRTUAL_FIELDS_MAP_[name]
            real_value = self.__getattribute__(real_field[0])
            return real_field[2](real_value)
        return super().__getattribute__(name)

    def __repr__(self):
        return f"<Controls: {self.make_dict()}>"

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self._lock.release()

    def set_controls(self, controls):
        with self._lock:
            if isinstance(controls, dict):
                for k, v in controls.items():
                    self.__setattr__(k, v)
            elif isinstance(controls, Controls):
                for k in controls._controls:
                    v = controls.__dict__[k]
                    self.__setattr__(k, v)
            else:
                raise RuntimeError(f"Cannot update controls with {type(controls)} type")

    """
    def get_libcamera_controls(self):
        def list_or_tuple(thing):
            return type(thing) in {list, tuple}

        libcamera_controls = {}
        with self._lock:
            for k in self._controls:
                v = self.__dict__[k]
                id = self._picam2.camera_ctrl_info[k][0]
                if id.type == ControlType.Rectangle:
                    # We can get a list of Rectangles or a single one.
                    if list_or_tuple(v) and v and list_or_tuple(v[0]):
                        v = [Rectangle(*i) for i in v]
                    else:
                        v = Rectangle(*v)
                elif id.type == ControlType.Size:
                    v = Size(*v)
                libcamera_controls[id] = v
        return libcamera_controls
    """

    def make_dict(self):
        dict_ = {}
        with self._lock:
            for k in self._controls:
                v = self.__dict__[k]
                dict_[k] = v
        return dict_