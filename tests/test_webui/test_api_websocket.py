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
from asyncio import Event

import pytest
from fastapi.testclient import TestClient

from app import App
from configuration.config_item import ConfigItem
from web_ui.senditem_websocket import WebSocketHandler, WebsocketManager
from web_ui.server import webui_app

client = TestClient(webui_app)


class TestItem(ConfigItem):
    data1: str = "test"
    data2: int = 1234


@pytest.fixture
def app():
    class TestApp(App):
        def __init__(self):
            super().__init__()
            # at the moment WebsocketManager only needs the suhdown event
            self._shutdown_event = Event()

    return TestApp()


@pytest.mark.asyncio
async def test_queue_manager(app):
    wsm = WebsocketManager(app)

    assert 0 == len(wsm._send_handlers)  # set should be empty

    handler1 = WebSocketHandler(wsm)

    assert 1 == len(wsm._send_handlers)

    handler2 = WebSocketHandler(wsm)

    assert 2 == len(wsm._send_handlers)

    item = TestItem()
    wsm.send_item(item)

    results = await asyncio.wait_for(handler1.next_item_json(), timeout=1)
    assert "testitem" in results

    results = await asyncio.wait_for(handler2.next_item_json(), timeout=1)
    assert "testitem" in results

    handler1.close()
    assert 1 == len(wsm._send_handlers)

    # add more handlers for shutdown test
    for i in range(10):
        wsm.add_handler(WebSocketHandler(wsm))

    await asyncio.wait_for(wsm._is_closed.wait(), timeout=1)
    assert 0 == len(wsm._send_handlers)
    assert wsm._is_closed.is_set()
    msg = await handler2.next_item_json()
    assert "shutdown" in msg


@pytest.mark.asyncio
async def test_websocket(app) -> None:
    wsm = WebsocketManager(app)
    ti = TestItem()
    with client.websocket_connect("/ws/upsync") as websocket:
        wsm.send_item(ti)
        data = websocket.receive_json()
        assert "testitem" in data

    # check that disconnect is handled correctly
    await asyncio.sleep(0.1)  # give the server time to handle the disconnect
    assert 0 == len(wsm._send_handlers)

    # test application shutdowm
    with client.websocket_connect("/ws/upsync") as websocket:
        app.shutdown_event.set()
        data = websocket.receive_json()
        assert "shutdown" in data

    await asyncio.wait_for(wsm._is_closed.wait(), timeout=1)
