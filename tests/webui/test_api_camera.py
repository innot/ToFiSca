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

import unittest

from fastapi.testclient import TestClient

from web_ui.server import webui_app

client = TestClient(webui_app)

class MyTestCase(unittest.TestCase):
    def test_roi(self) -> None:
        response = client.get("/api/camera/roi")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"top": 0.1, "bottom": 0.1, "left": 0.2, "right": 0.1},response.json())

if __name__ == '__main__':
    unittest.main()
