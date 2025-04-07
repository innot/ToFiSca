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
#  Copyright (c) 2022 by Thomas Holland, thomas@innot.de
#

import abc
import argparse
import asyncio
import logging
from abc import ABC
from typing import Optional, IO, Union, Callable

from prompt_toolkit import print_formatted_text, HTML, ANSI

"""
This class is a wrapper for the argparse.ArgumentParser module, 
"""


class CommandRoot:
    def __init__(self, *args, **kwargs):
        self.root = self
        self.parent = None
        self._parser = _PromptArgumentParser("", *args, **kwargs)
        self.title = None
        self.children = []
        self.title = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    @property
    def parser(self):
        return self._parser

    def add_child(self, child):
        self.children.append(child)

    def get_command_dict(self):
        result = {}
        for child in self.children:
            commands = child.get_command_dict()
            result.update(commands)

        return result

    def parse_args(self, *args):
        return self.parser.parse_args(*args)

    def find_parser(self, command: str) -> Union['CommandRoot', None]:
        # check if this is the parser node for the command
        if self.title == command:
            return self

        # no, then check the children
        for child in self.children:
            parser = child.find_parser(command)
            if parser:
                # found him
                return parser
        # did not find
        return None


class Command(CommandRoot):

    def __init__(self, parent, title: str, callback: Callable[[argparse.Namespace], None] = None, **kwargs):
        super().__init__()
        self.parent = parent
        self.root = parent.root
        self.title = title

        self.parent.add_child(self)
        self._parser = self.parent.parser.add_parser(title, **kwargs)
        if callback:
            self.parser.set_defaults(func=callback)

    def add_argument(self, *args, **kwargs):
        self.parser.add_argument(*args, **kwargs)

    def get_command_dict(self):
        if len(self.children) == 0:
            result = {self.title: None}
        else:
            sub_dicts = {}
            for child in self.children:
                sub_dicts.update(child.get_command_dict())
            result = {self.title: sub_dicts}

        return result


class Group(CommandRoot):
    def __init__(self, parent, **kwargs):
        super().__init__()
        self.parent = parent
        self.root = parent.root
        self.parent.add_child(self)

        self._parser = parent.parser.add_subparsers(**kwargs)

    def get_command_dict(self):
        commands = {}
        for child in self.children:
            commands.update(child.get_command_dict())
        return commands


class CommandParser:

    intro = "Generic command line interface"    # override by subclass
    prompt = "# "                               # dito

    def __init__(self, **kwargs):
        self._root: CommandRoot = CommandRoot(add_help=False, **kwargs)

        # add a subparser for all the different commands
        with Group(self.root, help="All commands") as g:
            self.basegroup = g
            # add the help command
            with Command(g, "help", self.helper, help="How to use the command line") as p:
                p.add_argument("command", nargs='*', help="Optional command name")

        # now add all of the user defined commands.
        # self.build_parser(self.basegroup)

    def helper(self, args):
        """
        Implement the help command.
        Outputs the parser generated help for the given command, or the global help if no arguments were given.
        :
        """
        try:
            command = args.command
            # find the parser for the command
            node = self.root
            while command:
                cmd = command.pop(0)
                node = node.find_parser(cmd)
            # end of the command line
            if node:
                # found a matching parser node
                node.parser.print_help()
                return

        except AttributeError:
            # no command argument was given to 'help'
            pass
        # just the global help
        parser = self.parser
        parser.print_help()

    @property
    def commandlist(self) -> dict:
        """
        Get a nested dictionary of all commands and subcommands.
        This dictionary can be used for the prompt_toolkit.NestedCompleter.
        :returns: Nested dict
        """
        all_commands = self.root.get_command_dict()
        copy = all_commands.copy()
        # Add a duplicate of the complete list to the entry for 'help'
        all_commands.pop('help')
        all_commands.update({'help': copy})
        return all_commands

    @property
    def root(self) -> CommandRoot:
        """
        The root node of the parser tree.
        Generated automatically at instantiation. Not settable.
        """
        return self._root

    @property
    def parser(self) -> argparse.ArgumentParser:
        """
        The base ArgumentParser for all options and arguments
        """
        return self._root.parser

    @abc.abstractmethod
    def build_parser(self, root: CommandRoot) -> None:
        # override in subclass
        pass

    async def execute(self, command: Union[str, list]) -> bool:
        if isinstance(command, str):
            command = command.split()
        try:
            args = self.parser.parse_args(command)

            # call the stored callback routine
            func = args.func
            if asyncio.iscoroutinefunction(func):
                await func(args)
            else:
                func(args)

        except AttributeError as err:
            # command not implemented
            logging.info(f"Internal error {err}")
            raise err
        except argparse.ArgumentError as err:
            self.print_html(f"<ansiyellow>{err.message}</ansiyellow>")

        return True

    ################################################################
    #
    # some useful methods for working with the prompt_toolkit
    #
    ################################################################

    # noinspection PyMethodMayBeStatic
    def print(self, *args):
        """Print the given text to the active prompt_toolkit session.
        :args: """
        print_formatted_text(*args, flush=True)

    # noinspection PyMethodMayBeStatic
    def print_html(self, html_text: str) -> None:
        html = HTML(html_text)
        print_formatted_text(html)

    # noinspection PyMethodMayBeStatic
    def print_ansi(self, ansi_text: str) -> None:
        ansi = ANSI(ansi_text)
        print_formatted_text(ansi)


class _PromptArgumentParser(argparse.ArgumentParser):
    """Slightly modified version of the default ArgumentParser to make it more suitable
    for a self contained command line interpreter.
    1. Inhibit programm exits by
        a. setting the 'exit_on_error' flag to False and
        b. overriding the exit() method.
    2. Redirect all output to the print_formatted() method of the prompt_toolkit.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exit_on_error = False

    # Overriding this method to redirect all output to the ssh connection.
    def _print_message(self, message: str, file: Optional[IO[str]] = ...) -> None:
        if message:
            print_formatted_text(message)

    # ArgumentParser has a tendency to exit, even with "exit_on_error" set to False,
    # e.g. after showing a help message.
    # Overriding this method to disregard a normal exit and to raise an Exception for errors.
    def exit(self, status=0, message=None):
        if status != 0:
            raise argparse.ArgumentError(None, message=message)
