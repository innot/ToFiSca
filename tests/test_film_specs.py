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

import unittest

from film_specs import FilmSpecs, film_specs, FilmFormat


class MyTestCase(unittest.TestCase):
    def test_get_all_keys(self):

        items = FilmSpecs.get_all_keys()
        self.assertTrue(isinstance(items, set))
        self.assertEqual(len(film_specs), len(items))
        self.assertTrue("super8" in items)

    def test_get_api_film_formats(self):
        result = FilmSpecs.get_api_film_formats()
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], FilmFormat)
        for item in result:
            self.assertTrue(len(item.key) > 1)
            self.assertTrue(len(item.name) > 1)
            self.assertTrue(len(item.framerates) > 0)

if __name__ == '__main__':
    unittest.main()
