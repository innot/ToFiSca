from enum import Enum

from pydantic import BaseModel


class Tags(Enum):
    GLOBAL = "global"
    GLOBAL_SETTING = "Global Setting"
    PROJECT_SETTING = "Project Setting"
    CAMERA = "camera"
    WEBSOCKET = "websocket"
