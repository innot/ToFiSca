"""
Example of running a prompt_toolkit application in an asyncssh server.
"""
import asyncio
import logging
import os
from asyncio import get_running_loop

import asyncssh
from prompt_toolkit import print_formatted_text, PromptSession, HTML
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.contrib.ssh import PromptToolkitSSHServer, PromptToolkitSSHSession
from prompt_toolkit.key_binding import KeyBindings

from sshPromptUI import CommandParser


class PromptUIApp:

    def __init__(self, commandparser: CommandParser = None, port: int = 8222, keyfile: str = None):
        if not commandparser:
            commandparser = CommandParser()  # default parser for testing

        self.cmdparser = commandparser
        self.port = port
        self._running = False

        if keyfile:
            self.host_keyfile = keyfile
        else:
            homedir = os.path.expanduser('~')
            self.host_keyfile = os.path.join(homedir, '.ssh_key')

    # noinspection PyMethodMayBeStatic
    def key_bindings(self) -> KeyBindings:
        # Key bindings.
        kb = KeyBindings()

        @kb.add("c-c")
        def _(event) -> None:
            logging.debug("SSH Server: Ctrl-C registered")
            try:
                # todo check if an interrupt can be send to a running process.
                # self.cmdparser.cmd_interrupt()
                pass
            except AttributeError:
                pass

        @kb.add("c-x")
        def _(event) -> None:
            logging.info("SSH Server: Ctrl-X registered")
            print_formatted_text("Session closed by user. Bye...")
            self.prompt_session.exit()

        return kb

    async def interact(self, ssh_session: PromptToolkitSSHSession) -> None:
        """
        The application interaction.
        This will run automatically in a prompt_toolkit AppSession, which means
        that any prompt_toolkit application (dialogs, prompts, etc...) will use the
        SSH channel for input and output.
        """
        logging.info("SSH Connection opened")
        self._running = True
        self.cmdparser.stdout = ssh_session.stdout

        all_commands = self.cmdparser.commandlist
        logging.info(f"Word Completer entries: {all_commands}")
        completer = NestedCompleter.from_nested_dict(all_commands)

        self.prompt_session = PromptSession(refresh_interval=0.5)

        kb = self.key_bindings()

        print_formatted_text(HTML(self.cmdparser.intro))
        prompt = HTML(self.cmdparser.prompt)

        while self._running:
            try:
                command = await self.prompt_session.prompt_async(prompt, key_bindings=kb, completer=completer)
                if command:
                    await self.cmdparser.execute(command)

            except KeyboardInterrupt:
                self._running = False
                logging.info("SSH Connection closed by Ctrl-X")
            except EOFError:
                logging.info("Ctrl-D received")

    async def start_server(self):
        logging.info("Starting ssh server")
        await asyncssh.create_server(
            lambda: PromptToolkitSSHServer(self.interact),
            "",
            self.port,
            server_host_keys=self._get_host_key(),
        )

    def _get_host_key(self) -> asyncssh.SSHKey:
        """load the private key for the SSH server.
        Default location is the file '.tofisca_ssh_key' file in the home directory of tofisca.
        Other location can be specified with the :meth:'keyfile' property (e.g. for testing).
        If the key file does not exist or is not a valid key a new private key is generated and
        saved.

        :return: the private key for the ssh server
        :rtype: asyncssh.SSHKey
        """
        try:
            key = asyncssh.read_private_key(self.host_keyfile)
        except (FileNotFoundError, asyncssh.KeyImportError):
            logging.info("SSH Server: No host key found or invalid - generating new one")
            key = asyncssh.generate_private_key('ssh-rsa', 'SSH Server Host Key for Tofisca')
            try:
                keyfile = open(self.host_keyfile, 'wb')
                keyfile.write(key.export_private_key())
                keyfile.close()
                logging.info(f"SSH Server: New private host key generated and saved as {self.host_keyfile}")
            except Exception as exc:
                logging.warning(f"SSH Server: could not write host key to {self.host_keyfile}. Reason: {exc}")

        return key

    async def run(self):
        loop = get_running_loop()
        loop.create_task(self.start_server())


if __name__ == "__main__":
    # Set up logging.
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)


    async def runner():

        app = PromptUIApp()
        ssh_task = asyncio.create_task(app.run())
        await asyncio.gather(ssh_task)

        print("SSH Server started")

        while 1:
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break


    asyncio.run(runner())
