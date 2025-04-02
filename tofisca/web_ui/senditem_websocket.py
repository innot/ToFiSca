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
#
from __future__ import annotations  # for forward referencing of types

import asyncio
import logging
from typing import Any, TypeAlias

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from tofisca import shutdown_event
from tofisca.configuration import ConfigItem

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

Payload: TypeAlias = dict[str, dict[str, Any]]


class WebSocketHandler:

    def __init__(self, qm: WebsocketManager):
        self._queue = asyncio.Queue()
        self._qm = qm
        self._qm.add_handler(self)

    async def next_item_json(self) -> Payload:
        payload: Payload = await self._queue.get()
        self._queue.task_done()
        return payload

    def enqueue(self, payload: Payload):
        self._queue.put_nowait(payload)

    def close(self):
        # to queue will continue to exist while serving out the outstanding items and a potential shutdown message
        # todo: when upgrading to python 3.13 use queue.shutdown()
        self._qm.remove_handler(self)


class WebsocketManager:

    _instance: WebsocketManager = None

    def __new__(cls) -> WebsocketManager:
        # Check if the class has already been instantiated.
        # If yes return the class Singleton
        if cls._instance:
            return cls._instance

        cls._instance = super(WebsocketManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def delete_singleton(cls):
        """
        Delete the Singleton ConfigDatabase instance so a new instance can be created.
        This is supposed to be used for unit testing.
        """
        cls._db_instance = None

    def __init__(self):
        self._send_handlers: set[WebSocketHandler] = set()
        self._shutdown_wait_task = asyncio.create_task(self._wait_for_shutdown())
        self._shutdown_wait_task.add_done_callback(lambda _: None)  # just to clean up
        self._is_closed = asyncio.Event()

    async def _wait_for_shutdown(self):
        await shutdown_event.wait()
        self.close()

    def add_handler(self, handler: WebSocketHandler) -> None:
        if self._is_closed.is_set():
            raise RuntimeError("Cannot add handler to closed WebsocketManager")
        self._send_handlers.add(handler)

    def remove_handler(self, handler: WebSocketHandler) -> None:
        if self._is_closed.is_set():
            raise RuntimeError("Cannot remove handler to closed WebsocketManager")
        self._send_handlers.remove(handler)

    def send_item(self, item: ConfigItem) -> None:
        """
        Send a ConfigItem to the Frontend.

        The item is converted into a JSON object, enqueued in the transmit queue, and asynchronously
        send to the frontend.

        After closing
        """
        if self._is_closed.is_set():
            raise RuntimeError("Cannot send item to closed WebsocketManager")
        payload = {item.get_qualified_name(): item.model_dump()}
        for handler in self._send_handlers:
            handler.enqueue(payload)

    def item_change_callback(self, item, name, old_value, new_value):
        if self._is_closed.is_set():
            raise RuntimeError("Cannot send item to closed WebsocketManager")
        # todo: should we send just the changed data?
        self.send_item(item)

    def close(self):
        """
        Close the QueueManager.
        Tis will send a shutdown message to all registered websocket handlers.
        """
        self._shutdown_wait_task.cancel()      # in case the shutdown came not from the shutdown_event
        handlers_copy = list(self._send_handlers)   # _send_handlers will be mutated by the handlers closing
        for handler in handlers_copy:
            message = {"shutdown": {"message": "ToFiSca Application has shutdown"}}
            handler.enqueue(message)
            handler.close() # the queue lives on until the handler is garbage collected
        self._is_closed.set()

def websocket_setup():
    global transmit_websocket
    transmit_websocket = WebsocketManager()

transmit_websocket: WebsocketManager | None = None


@router.websocket("/ws/upsync")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    logger.debug(f"websocket accepted from {client.host}:{client.port}")
    handler = WebSocketHandler(WebsocketManager())
    try:
        while True:
            item = await handler.next_item_json()
            await websocket.send_json(item)
    except WebSocketDisconnect:
        logger.debug("websocket connection closed by client")
        handler.close()

