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
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from mock_picamera2.outputs.fileoutput import FileOutput


class JpegEncoder:

    def __init__(self, num_threads=4, q=None, colour_space=None, colour_subsampling='420'):
        self._lock = threading.Lock()
        self._output_lock = threading.Lock()
        self._running = False
        self._config: dict = {}
        self.threads = ThreadPoolExecutor(num_threads)
        self.tasks = queue.Queue()

    @property
    def config(self) -> dict:
        return self.config

    @config.setter
    def config(self, config) -> None:
        self._config = config

    @property
    def output(self):
        """Gets output objects

        :return: Output object list or single Output object
        :rtype: List[Output]
        """
        if len(self._output) == 1:
            return self._output[0]
        else:
            return self._output

    @output.setter
    def output(self, value):
        """Sets output object, to write frames to

        :param value: Output object
        :type value: Output
        :raises RuntimeError: Invalid output passed
        """
        if isinstance(value, list):
            for out in value:
                if not isinstance(out, FileOutput):
                    raise RuntimeError("Must pass Output")
        elif isinstance(value, FileOutput):
            value = [value]
        else:
            raise RuntimeError("Must pass Output")
        self._output = value

    def start(self, quality=None):
        with self._lock:
            if self._running:
                raise RuntimeError("Encoder already running")
            self._running = True

            for output in self._output:
                output.start()

            self.thread = threading.Thread(target=self.output_thread, daemon=True)
            self.thread.start()

    def stop(self):
        with self._lock:
            if not self._running:
                raise RuntimeError("Encoder already stopped")
            self._running = False
            self.tasks.put(None)
            self.thread.join()

    def output_thread(self):
        """Outputs frame"""
        while True:
            array = self.tasks.get()
            if array is None:
                return

            is_success, buffer = cv2.imencode(".jpg", array)

            with self._output_lock:
                for out in self._output:
                    out.outputframe(buffer.tobytes())


    def encode_image(self, array: np.ndarray):
        self.tasks.put(array)
