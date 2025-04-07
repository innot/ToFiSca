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
from asyncio import CancelledError, Task, Event
from typing import Any, TypeAlias, Self

from fastapi import APIRouter, WebSocket, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from configuration.config_item import ConfigItem

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

Payload: TypeAlias = dict[str, dict[str, Any]]


class WebSocketHandler:
    """
    This class is the interface between a websocket connection and the :class:`WebSocketManager`

    They are basically just a queue that will receive items from the WebSocketManager
    that in turn will be picked up by the :meth:`websocket_endpoint` to send to the frontend.
    """

    def __init__(self, qm: WebSocketManager):
        self._queue = asyncio.Queue()
        self._qm = qm
        self._qm.add_handler(self)
        self.is_closed: Event = Event()

    async def next_item_json(self) -> Payload:
        payload: Payload = await self._queue.get()
        self._queue.task_done()
        return payload

    def enqueue_json(self, payload: Payload):
        self._queue.put_nowait(payload)

    def enqueue_item(self, item: BaseModel):
        item_json = jsonable_encoder(item)
        self.enqueue_json(item_json)

    def close(self):
        # the queue will continue to exist while serving out the outstanding items and a potential shutdown message
        # todo: when upgrading to python 3.13 use queue.shutdown()
        self.is_closed.set()
        self._qm.remove_handler(self)


class WebSocketManager:
    """
    The Manager is the central point to send items to all connected Websockets.

    It is used as a singleton, i.e. there is only one instance that must be accessed
    via :meth:`get_manager`.

    New connections create :class:`WebSocketHandler` objects which are registered with this manager
    and which will in turn receive the items to send from the manager.
    """
    _instance: WebSocketManager | None = None

    @classmethod
    def get_manager(cls) -> Self:
        if cls._instance is None:
            cls._instance = WebSocketManager()
        return cls._instance

    def __init__(self):
        from web_ui.server import get_app
        self._app = get_app()
        self._send_handlers: set[WebSocketHandler] = set()
        self._shutdown_wait_task = asyncio.create_task(self._wait_for_shutdown())
        self._shutdown_wait_task.add_done_callback(self.shutdown_cb)  # just to clean up
        self.is_closed = asyncio.Event()

    async def _wait_for_shutdown(self):
        event = self._app.shutdown_event
        await event.wait()
        self.close()

    @staticmethod
    def shutdown_cb(task: Task):
        # this method is here to have a place to catch programming errors
        # todo: handle Cancelled
        exc = task.exception()
        logger.error(exc)

    def add_handler(self, handler: WebSocketHandler) -> None:
        if self.is_closed.is_set():
            raise RuntimeError("Cannot add handler to closed WebsocketManager")
        self._send_handlers.add(handler)

    def remove_handler(self, handler: WebSocketHandler) -> None:
        if self.is_closed.is_set():
            raise RuntimeError("Cannot remove handler to closed WebsocketManager")
        self._send_handlers.remove(handler)

    def send_item(self, item: ConfigItem) -> None:
        """
        Send a ConfigItem to the Frontend.

        The item is converted into a JSON object, enqueued in the transmit queue, and asynchronously
        send to the frontend.
        """
        if self.is_closed.is_set():
            raise RuntimeError("Cannot send item to closed WebsocketManager")
        payload = {item.get_qualified_name(): jsonable_encoder(item)}
        for handler in self._send_handlers:
            handler.enqueue_json(payload)

    def item_change_callback(self, item, *_) -> None:
        """
        A callback function that is called from :class:`FieldChangedObserverMixin` :class:`ConfigItem` to
        automatically send any changes to the frontend.

        This will always send the complete item.

        :param item: The :class:`ConfigItem` to send.
        """
        if self.is_closed.is_set():
            raise RuntimeError("Cannot send item to closed WebsocketManager")
        self.send_item(item)

    def close(self):
        """
        Close the QueueManager.
        This will send a shutdown message to all registered websocket handlers.
        """
        if not self.is_closed.is_set():  # in case this is called multiple times
            self._shutdown_wait_task.cancel()  # in case the shutdown came not from the shutdown_event
            handlers_copy = list(self._send_handlers)  # _send_handlers will be mutated by the handlers closing
            for handler in handlers_copy:
                handler.close()  # the queue lives on until the handler is garbage collected
            self.is_closed.set()


@router.websocket("/ws/upsync")
async def websocket_endpoint(websocket: WebSocket):
    wsm = WebSocketManager.get_manager()

    try:
        handler = WebSocketHandler(wsm)
    except RuntimeError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="ToFiSca Application has shut down.")

    await websocket.accept()

    client = websocket.client
    if client is not None:
        logger.debug(f"websocket accepted from {client.host}:{client.port}")
    else:
        logger.debug(f"websocket accepted")

    disconnect_check_task = asyncio.create_task(websocket.receive())
    shutdown_check_task = asyncio.create_task(handler.is_closed.wait())
    while True:
        next_item_task = asyncio.create_task(handler.next_item_json())
        done, pending = await asyncio.wait(
            [disconnect_check_task, shutdown_check_task, next_item_task],
            return_when=asyncio.FIRST_COMPLETED)

        if next_item_task.done():
            # we got a new item to send
            item = next_item_task.result()
            await websocket.send_json(item)

        if shutdown_check_task.done():
            message = {"shutdown": {"message": "ToFiSca Application has shutdown"}}
            await websocket.send_json(message)
            logger.info("websocket connection closed by shutdown event")

        if disconnect_check_task.done():
            handler.close()
            logger.debug("websocket connection closed by client")

        # if either disconnected or shutdown: cancel all other tasks and exit the loop
        if disconnect_check_task.done() or shutdown_check_task.done():
            for task in pending:
                task.cancel()
                try:
                    await task
                except CancelledError:
                    pass
            break

    pass
