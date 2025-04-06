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
from typing import Union, ClassVar, Self

from pydantic import BaseModel, Field, model_validator


class APIError(BaseModel):
    error_type: str = Field(default="", description="Error type. The class name of the error")
    status_code: ClassVar[int] = 400
    title: str = Field(description="Human-readable error title")
    details: str = Field(default="No details available", description="Detailed description")
    stacktrace: str = Field(default="", description="Stack trace. Only for unhandled exceptions.")

    @model_validator(mode="after")
    def set_error_type(self) -> Self:
        """
        If the error_type has not been set, update it to the class name of the actual class.
        """
        if self.error_type == "":
            self.error_type = self.__class__.__name__
        return self

class APIObjectNotFoundError(APIError):
    status_code: ClassVar[int] = 404

class APIInvalidDataError(APIError):
    status_code: ClassVar[int] = 422

class APIProjectDoesNotExist(APIError):
    status_code: ClassVar[int] = 404
    title: str = "Project does not exist"
    identifier: Union[int, str] = Field(exclude=True)

    @model_validator(mode="after")
    def update_details(self) -> Self:
        type_str = 'name' if isinstance(self.identifier, str) else 'project id'
        self.details = f"No project with the {type_str} '{self.identifier}' exists in ToFiSca."
        return self


class APINoActiveProject(APIError):
    status_code: ClassVar[int] = 404
    title: str = "No active project"
    details: str = "No Project has been loaded. Please load a project first."


class APIProjectAlreadyExists(APIError):
    status_code: ClassVar[int] = 409
    title: str = "Project already exists"
    name: str = Field(exclude=True)

    @model_validator(mode="after")
    def update_details(self) -> Self:
        self.details = f"A project with the name '{self.name}' exists in ToFiSca. Please use a different name."
        return self
