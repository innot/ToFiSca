import shutil
import tempfile
import unittest
from pathlib import Path

from tofisca.configuration import ConfigDatabase
from tofisca.errors import ProjectAlreadyExistsError
from tofisca import ProjectManager


class TestProjectManager(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        ConfigDatabase("memory")

    async def asyncTearDown(self):
        pass

    def test_create_project(self):
        project = ProjectManager.create_project("test_1")
        self.assertIsNotNone(project)
        self.assertEqual("test_1", ProjectManager.active_project.name)
        self.assertTrue((ProjectManager.projects_directory / "test_1").exists)
        self.assertTrue((ProjectManager.projects_directory / "test_1").is_dir())

        # create a different project
        project = ProjectManager.create_project("test_2")
        self.assertIsNotNone(project)
        self.assertEqual("test_2", ProjectManager.active_project.name)

        # create an already existing project - throw error
        with self.assertRaises(ProjectAlreadyExistsError):
            ProjectManager.create_project("test_1")

        # create a temporary project, check that it is in the system temp folder
        project = ProjectManager.create_project("test_3", tmp=True)
        self.assertIsNotNone(project)
        self.assertEqual("test_3", ProjectManager.active_project.name)

        path = Path(tempfile.gettempdir()) / "tofisca" / "test_3"
        self.assertTrue(path.exists() and path.is_dir())
        try:
            project = ProjectManager.create_project("test_3", tmp=True)
            self.assertIsNotNone(project)
            self.assertEqual("test_3", ProjectManager.active_project.name)
        except ProjectAlreadyExistsError:
            self.fail()

    async def test_list_projects(self):
        # first create a few projects
        proj_list = ["test_a", "test_b", "test_c"]
        for proj_name in proj_list:
            await ProjectManager.create_project(proj_name)

        lp = await ProjectManager.list_projects()
        self.assertCountEqual(lp, proj_list)
        for item in lp:
            self.assertTrue(item.name in proj_list)


if __name__ == '__main__':
    unittest.main()

