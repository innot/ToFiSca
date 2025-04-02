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
import unittest

from fastapi.testclient import TestClient

import utils.event_threadsafe as globals
from tofisca.configuration import ConfigItem, ConfigDatabase
from web_ui.senditem_websocket import WebSocketHandler, WebsocketManager
from web_ui.server import webui_app

client = TestClient(webui_app)


class TestItem(ConfigItem):
    data1: str = "test"
    data2: int = 1234


class MyTestCase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        ConfigDatabase("memory")
        globals.shutdown_event = asyncio.Event()

    async def asyncTearDown(self):
        ConfigDatabase.delete_singleton()
        WebsocketManager.delete_singleton()

    async def test_queue_manager(self):
        wsm = WebsocketManager()
        self.assertFalse(wsm._send_handlers)  # set should be empty

        # test singleton
        self.assertTrue(wsm is WebsocketManager())

        handler1 = WebSocketHandler(wsm)
        self.assertTrue(len(wsm._send_handlers) == 1)

        handler2 = WebSocketHandler(wsm)
        self.assertTrue(len(wsm._send_handlers) == 2)

        item = TestItem()
        wsm.send_item(item)

        results = await asyncio.wait_for(handler1.next_item_json(), timeout=1)
        self.assertIsNotNone(results)
        self.assertTrue("testitem" in results)

        results = await asyncio.wait_for(handler2.next_item_json(), timeout=1)
        self.assertIsNotNone(results)
        self.assertTrue("testitem" in results)

        handler1.close()
        self.assertTrue(len(wsm._send_handlers) == 1)

        # add more handlers for shutdown test
        for i in range(10):
            wsm.add_handler(WebSocketHandler(wsm))

        shutdown_event.set()
        await asyncio.wait_for(wsm._is_closed.wait(), timeout=1)
        self.assertTrue(len(wsm._send_handlers) == 0)
        self.assertTrue(wsm._is_closed.is_set())
        msg = await handler2.next_item_json()
        self.assertIn("shutdown", msg)

    async def test_websocket(self) -> None:
        wsm = WebsocketManager()
        ti = TestItem()
        with client.websocket_connect("/ws/upsync") as websocket:
            wsm.send_item(ti)
            data = websocket.receive_json()
            self.assertIn("testitem", data)

        # check that disconnect is handled correctly
        await asyncio.sleep(0.1)  # give the server time to handle the disconnect
        self.assertTrue(len(wsm._send_handlers) == 0)

        # test application shutdowm
        with client.websocket_connect("/ws/upsync") as websocket:
            shutdown_event.set()
            data = websocket.receive_json()
            self.assertIn("shutdown", data)

        await asyncio.wait_for(wsm._is_closed.wait(), timeout=1)


if __name__ == '__main__':
    unittest.main()
