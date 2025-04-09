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
import io
from pathlib import Path


class FileOutput:
    def __init__(self, file=None, pts=None, split=None):
        self.recording = False
        self.fileoutput = file
        self._firstframe = True

    @property
    def fileoutput(self):
        """Return file handle"""
        return self._fileoutput

    @fileoutput.setter
    def fileoutput(self, file):
        """Change file to output frames to"""
        self._firstframe = True
        self._needs_close = False
        if file is None:
            self._fileoutput = None
        else:
            if isinstance(file, str) or isinstance(file, Path):
                self._fileoutput = open(file, "wb")
                self._needs_close = True
            elif isinstance(file, io.BufferedIOBase):
                self._fileoutput = file
            else:
                raise RuntimeError("Must pass io.BufferedIOBase")

    def start(self):
        """Start recording"""
        self.recording = True

    def stop(self):
        """Stop recording"""
        self.recording = False
        self.close()

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        if self._fileoutput is not None and self.recording:
            if self._firstframe:
                if not keyframe:
                    return
                else:
                    self._firstframe = False
            self._write(frame)

    def close(self):
        """Closes all files"""
        if self._needs_close:
            self._fileoutput.close()

    def _write(self, frame):
        self._fileoutput.write(frame)
        self._fileoutput.flush()

