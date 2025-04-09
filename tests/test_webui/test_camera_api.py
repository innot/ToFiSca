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
from io import BytesIO

import pytest
from PIL import Image
from async_asgi_testclient import TestClient

from main import MainApp
from web_ui.server import webui_app, set_app


@pytest.fixture(scope="session")
def client(tmp_path_factory) -> TestClient:
    app = MainApp(data_storage_path=tmp_path_factory.mktemp("test", numbered=True),
                  database_file="memory")
    set_app(app)

    client = TestClient(webui_app)
    return client


@pytest.mark.asyncio
async def test_get_camera_preview(client):
    response = await client.get("/api/camera/preview")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-cache"
    assert int(response.headers["content-length"]) > 0

    image = Image.open(BytesIO(response.content))
    assert image.mode == "RGB"
    assert image.size[0] > 0 and image.size[1] > 0

    # image.show()


@pytest.mark.asyncio
async def test_get_camera_live(client):
    counter = 0
    response = await client.get("/api/camera/live", stream=True)
    assert response.status_code == 200
    assert response.headers["content-type"] == 'multipart/x-mixed-replace; boundary=---frame'

    # todo: test if we receive images - but that is non-trivial

