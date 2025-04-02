from .utils import Event_ts
from .project import Project


shutdown_event: Event_ts | None = None
"""
When set causes all parts of the application to shut down, saving their state as required.
The application exits after that.
"""
