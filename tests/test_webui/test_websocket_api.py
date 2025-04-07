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
import asyncio

import pytest
import pytest_asyncio
from async_asgi_testclient import TestClient

from configuration.config_item import ConfigItem
from main import MainApp
from web_ui.server import webui_app, set_app, get_app
from web_ui.websocket_api import WebSocketHandler, WebSocketManager


class SampleItem(ConfigItem):
    data1: str = "test"
    data2: int = 1234


@pytest_asyncio.fixture
async def client(tmp_path_factory):
    app = MainApp(data_storage_path=tmp_path_factory.mktemp("test", numbered=True),
                  database_file="memory")
    set_app(app)

    async with TestClient(webui_app) as client:
        yield client


@pytest.mark.asyncio
async def test_queue_manager(client):
    wsm = WebSocketManager.get_manager()

    assert len(wsm._send_handlers) == 0  # set should be empty

    handler1 = WebSocketHandler(wsm)

    assert len(wsm._send_handlers) == 1

    handler2 = WebSocketHandler(wsm)

    assert len(wsm._send_handlers) == 2

    item = SampleItem()
    wsm.send_item(item)

    results = await asyncio.wait_for(handler1.next_item_json(), timeout=1)
    assert "sampleitem" in results

    results = await asyncio.wait_for(handler2.next_item_json(), timeout=1)
    assert "sampleitem" in results

    handler1.close()
    assert len(wsm._send_handlers) == 1

    # send shutdown signal
    get_app().shutdown_event.set()

    await asyncio.wait_for(wsm.is_closed.wait(), timeout=1)
    assert 0 == len(wsm._send_handlers)
    assert wsm.is_closed.is_set()

    # need to clean up the WebSocketManager for the next test
    WebSocketManager._instance = None


@pytest.mark.asyncio
async def test_websocket(client) -> None:
    ti = SampleItem()

    wsm = WebSocketManager.get_manager()  # get the WebSocketManager from the server

    async with client.websocket_connect("/ws/upsync") as websocket:
        wsm.send_item(ti)
        result = await asyncio.wait_for(websocket.receive_json(), timeout=1)
        assert "sampleitem" in result

    # check that disconnect is handled correctly
    await asyncio.sleep(0.1)  # give the server time to handle the disconnect
    assert len(wsm._send_handlers) == 0

    # test application shutdowm
    async with client.websocket_connect("/ws/upsync") as websocket:
        get_app().shutdown_event.set()
        result = await asyncio.wait_for(websocket.receive_json(), timeout=1)
        assert "shutdown" in result

    try:
        await asyncio.wait_for(wsm.is_closed.wait(), timeout=1)
    except asyncio.TimeoutError:
        assert False

    # check that connection after shutdown is refused
    with pytest.raises(AssertionError):
        async with client.websocket_connect("/ws/upsync"):
            # The server raises an HTTPException
            # async_asgi_testclient fails with an assertion error
            pass
