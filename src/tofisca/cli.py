import logging

from project_manager import ProjectManager, ProjectAlreadyExistsError
from sshPromptUI import PromptUIApp
from argparsedecorator import ArgParseDecorator


class TofiscaCLI:
    intro = "<ansigreen>ToFiSca Command Line Interface\r\n" \
            "Use <ansicyan>help</ansicyan> for a list of supported commands.\r\n" \
            "Press <ansiblue>Ctrl-X</ansiblue> to end this session.</ansigreen>\r\n"

    prompt = "<ansigreen>tofisca# </ansigreen>"

    parser = ArgParseDecorator("")

    @parser.command()
    def project_new(self, args):
        """
        Create a new project.
        arguments::
            projectname :: The name of the new project. Must be a valid filename.
            -t, --temp :True :: If set the project is created in the temp folder.
        """
        logging.info(f"New Project: name '{args.projectname}', temporary {args.temp} ")
        projectname = args.projectname
        temp_flag = args.temp
        # todo sanitize filename
        try:
            project = ProjectManager.create_project(projectname, tmp=temp_flag)
            self.print_html(f"<ansigreen>Project {project.name} has been created and is active.</ansigreen>")
        except ProjectAlreadyExistsError:
            self.print_html(
                f"<ansired>A project with the name <ansicyan>{projectname}</ansicyan> already exists.</ansired>")
        except (FileNotFoundError, FileExistsError) as exc:
            self.print_html("<ansired>Something went wrong. Here is the internal error message:</ansired>")
            self.print_html(f"<ansiyellow>{exc}</ansiyellow>")

    @parser.command()
    def list_projects(self, _):
        project_list = ProjectManager.all_projects()
        if project_list:
            [self.print(name) for name in project_list]
        else:
            self.print("No projects yet")

    def load_project(self, args):
        pass

    def do_led(self, args):
        """Switch the backlight LED on or off.
        usage: led on|off [brightness%] [time_ms]
        """
        pass

    def do_feed(self, args):
        """Drive the feed stepper motor. If no steps are given transport one full frame.
        usage: feed [steps]
        """
        pass

    def do_load(self, args):
        """Load a project.
        usage: load projectname"""
        pass

    def do_run(self, args):
        """Start or continue the current project.
        usage: run
        """
        pass

    def do_pause(self, args):
        """Pause the currently running project. The current frame scan is completed first.
        usage: pause
        """
        pass

    def do_snap(self, args):
        """Makes a single camera picture and stores it.
        usage: snap [filename]
        """
        pass

    def do_test(self, args) -> None:
        """Just a Test function"""
        self.print(f"Test called with {args}")

    def do_exit(self, _) -> bool:
        """End telnet session."""
        self.print("Session closed by user")
        logging.debug("ssh command [exit]")
        return True

    def do_shutdown(self, args):
        """shutdown [now]
        Stop the ToFiSca application as soon as any pending jobs (scans, saves) are completed.
        If the optional argument 'now' is given ToFiSca is shut down immediatley.
        """
        if args[0] == "now":
            self.print("Stopping ToFiSca immediatley")
            # tofisca.ProjectManager.stop(now=True)
        else:
            self.print("Shutting down ToFiSca")
            # tofisca.ProjectManager.stop()


if __name__ == "__main__":
    import asyncio

    # Set up logging.
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)


    async def runner():

        app = PromptUIApp(commandparser=TofiscaCLI())
        ssh_task = asyncio.create_task(app.run())
        await asyncio.gather(ssh_task)

        print("SSH Server started")

        while 1:
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break


    asyncio.run(runner())
