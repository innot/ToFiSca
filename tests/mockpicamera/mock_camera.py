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
from queue import Queue
from threading import Thread

from film_generator import TestFrameGenerator
from mock_controls import Controls


class Camera:

    def __init__(self):
        self.generator = TestFrameGenerator()

        self.listener_thread: Thread | None = None
        self.request_queue = Queue()
        self.result_queue = Queue()

    def start(self, controls: Controls):
        if not self.listener_thread:
            self.listener_thread = Thread(target=self.listener, daemon=True)
            self.listener_thread.start()

    def stop(self):
        self.request_queue.put(Request("stop", None))
        self.listener_thread.join()

    def queue_request(self, request: Request):
        pass

    def create_request(self) -> Request:
        return Request()

    def listener(self):

        while True:
            request = self.request_queue.get()
            if request.type == "stop":
                return
