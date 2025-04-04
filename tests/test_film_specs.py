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

from film_specs import FilmSpecs, film_specs, FilmFormat


def test_get_all_keys():
    items = FilmSpecs.get_all_keys()
    assert isinstance(items, set)
    assert len(film_specs) == len(items)
    assert "super8" in items


def test_get_api_film_formats():
    result = FilmSpecs.get_api_film_formats()
    assert isinstance(result, list)
    assert isinstance(result[0], FilmFormat)
    for item in result:
        assert len(item.key) > 1
        assert len(item.name) > 1
        assert len(item.framerates) > 0
