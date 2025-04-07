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
import logging


class Event_ts(asyncio.Event):

    def set(self):
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(super().set)

    def clear(self):
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(super().clear)

    async def wait(self):
        loop = asyncio.get_event_loop()
        logging.info(f"Event_ts wait: {id(loop)}")
        await super().wait()
