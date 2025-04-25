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
import logging

from fastapi import APIRouter

from hardware_manager import HardwareManager, BacklightController, PinInfo
from web_ui import Tags

logger = logging.getLogger(__name__)


def get_hardware_manager() -> HardwareManager:
    """
    Get the CameraManager from the running Application.
    """
    from web_ui.server import get_app
    app = get_app()
    return app.hardware_manager


router = APIRouter()


@router.get("/api/hardware/allgpios",
            tags=[Tags.HARDWARE])
async def get_allgpios() -> list[PinInfo]:
    hm = get_hardware_manager()
    gpios = hm.all_gpios
    return gpios


@router.get("/api/hardware/backlight",
            tags=[Tags.HARDWARE], )
async def get_backlight() -> BacklightController:
    hm = get_hardware_manager()
    blc = hm.backlight
    return blc


@router.put("/api/hardware/backlight",
            tags=[Tags.HARDWARE], )
async def put_backlight(gpio: int | None = None,
                        enable: bool | None = None,
                        frequency: int | None = None,
                        dutycycle: float | None = None,
                        invert: bool | None = None) -> BacklightController:
    hm = get_hardware_manager()
    blc = hm.backlight
    if gpio is not None:
        blc.gpio = gpio
    if invert is not None:
        blc.invert = invert
    if frequency is not None:
        blc.frequency = frequency
    if dutycycle is not None:
        blc.dutycycle = dutycycle
    if enable is not None:
        blc.enable = enable

    await blc.store(hm.app.config_database)
    return blc
