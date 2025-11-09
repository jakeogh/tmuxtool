#!/usr/bin/env python3

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from signal import SIG_DFL
from signal import SIGPIPE
from signal import signal

import click
import hs
import psutil
from asserttool import ic
from asserttool import icp
from asserttool import maxone
from click_auto_help import AHGroup
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tvicgvd
from eprint import eprint
from globalverbose import gvd
from mptool import output

signal(SIGPIPE, SIG_DFL)


def in_tmux():
    try:
        print("os.environ['TMUX']:", os.environ["TMUX"])
    except KeyError:
        raise ValueError("start tmux!")


class MultiPaneSession:
    """
    Manage a tmux session with multiple panes.

    Example:
        with MultiPaneSession("myserver", "mysession", layout="tiled") as session:
            session.add_pane("/usr/bin/greendb", "-c", "/path/config.json", title="db1")
            session.add_pane("/usr/bin/greendb", "-c", "/path/config2.json", title="db2")
    """

    def __init__(
        self,
        server_name: str,
        session_name: str,
        layout: str = "tiled",
        force_new: bool = False,
    ):
        """
        Create or attach to tmux session for multi-pane management.

        Args:
            server_name: tmux server name (-L flag)
            session_name: session identifier
            layout: tmux layout (tiled, main-vertical, even-horizontal, etc.)
            force_new: if True, kill existing session and create new
        """
        self.server_name = server_name
        self.session_name = session_name
        self.layout = layout
        self.current_window = None
        self.pane_count = 0

        # Start server if not running
        hs.Command("tmux")(
            "-L",
            server_name,
            "start-server",
        )

        # Handle force_new
        if force_new:
            try:
                hs.Command("tmux")(
                    "-L",
                    server_name,
                    "kill-session",
                    "-t",
                    session_name,
                )
            except hs.ErrorReturnCode:
                pass  # Session didn't exist, that's fine

        # Create session if it doesn't exist
        try:
            hs.Command("tmux")(
                "-L",
                server_name,
                "has-session",
                "-t",
                session_name,
            )
            # Session exists, we'll attach to it
        except hs.ErrorReturnCode:
            # Session doesn't exist, create it with a dummy command
            hs.Command("tmux")(
                "-L",
                server_name,
                "new-session",
                "-d",
                "-s",
                session_name,
                "sleep",
                "infinity",  # Placeholder, will be replaced by first add_pane
            )

        # Set options
        hs.Command("tmux")(
            "-L",
            server_name,
            "set-option",
            "-t",
            session_name,
            "remain-on-exit",
            "failed",
        )

        self.current_window = self._get_current_window()

    def _get_current_window(self) -> str:
        """Get the current window identifier."""
        result = hs.Command("tmux")(
            "-L",
            self.server_name,
            "display-message",
            "-t",
            self.session_name,
            "-p",
            "#{window_id}",
        ).strip()
        return result

    def _tmux(self, *args):
        """Execute tmux command with server and session context."""
        return hs.Command("tmux")(
            "-L",
            self.server_name,
            *args,
        )

    def add_pane(
        self,
        *command: str,
        title: str | None = None,
        window: str | None = None,
    ) -> str:
        """
        Add a window and immediately start the command.

        Args:
            *command: Command and arguments as separate strings
            title: Optional window name
            window: Optional window name (if None, auto-generates)

        Returns:
            window_id: tmux window identifier
        """
        if not command:
            raise ValueError("Command cannot be empty")

        # Auto-generate window name if not provided
        if window is None:
            window = title or f"win-{self.pane_count}"

        # If this is the first window, respawn it instead of creating new
        if self.pane_count == 0:
            target = f"{self.session_name}:{self.current_window}.0"
            self._tmux(
                "respawn-pane",
                "-t",
                target,
                "-k",
                *command,
            )
            window_id = self._tmux(
                "display-message", "-t", target, "-p", "#{window_id}"
            ).strip()
            # Rename the window if title provided
            if title is not None:
                self._tmux(
                    "rename-window",
                    "-t",
                    window_id,
                    title,
                )
        else:
            # Create new window
            window_id = self._tmux(
                "new-window",
                "-t",
                self.session_name,
                "-n",
                window,
                "-d",
                "-P",
                "-F",
                "#{window_id}",
                *command,
            ).strip()

        self.pane_count += 1
        return window_id

    def _ensure_window(self, window_name: str):
        """Ensure window exists and switch to it."""
        # Check if window exists
        try:
            result = self._tmux(
                "list-windows",
                "-t",
                self.session_name,
                "-F",
                "#{window_name}",
            )
            windows = result.strip().split("\n")
            if window_name in windows:
                # Window exists, switch to it
                self._tmux(
                    "select-window",
                    "-t",
                    f"{self.session_name}:{window_name}",
                )
                self.current_window = window_name
                return
        except hs.ErrorReturnCode:
            pass

        # Window doesn't exist, create it
        self.new_window(window_name)

    def new_window(self, name: str) -> str:
        """
        Create a new window and switch to it for subsequent add_pane() calls.

        Args:
            name: window name

        Returns:
            window_id: tmux window identifier
        """
        window_id = self._tmux(
            "new-window",
            "-t",
            self.session_name,
            "-n",
            name,
            "-d",
            "-P",
            "-F",
            "#{window_id}",
            "sleep",
            "infinity",  # Placeholder for first pane
        ).strip()

        self.current_window = name
        self.pane_count = 0  # Reset pane count for new window

        return window_id

    def apply_layout(self, layout: str | None = None):
        """
        Re-apply layout to current window.

        Args:
            layout: Override initial layout, or None to use __init__ layout
        """
        layout_to_use = layout if layout is not None else self.layout

        try:
            self._tmux(
                "select-layout",
                "-t",
                f"{self.session_name}:{self.current_window}",
                layout_to_use,
            )
        except hs.ErrorReturnCode as e:
            # Layout might fail with certain pane counts, that's OK
            ic(f"Layout application failed (might be OK): {e}")

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):
        # Apply final layout on exit
        self.apply_layout()
        return False


def launch_tmux(
    *,
    server_name: str,
    arguments: list | tuple,
):
    assert isinstance(arguments, (list, tuple))
    hs.Command("tmux")(
        "-L",
        server_name,
        "start-server",
    )
    hs.Command("tmux")(
        "-L",
        server_name,
        "set-option",
        "-g",
        "remain-on-exit",
        "failed",
    )

    xterm_process = hs.xterm.bake(
        "-e",
        "tmux",
        "-L",
        server_name,
        "new-session",
        "-d",
        *arguments,
    )

    ic(xterm_process)

    xterm_process(_bg=True, _bg_exc=True)


def list_tmux(
    *,
    server_name: str,
    show_command: bool,
    only_detached: bool,
    only_attached: bool,
):
    ic(server_name)
    maxone([only_attached, only_detached])

    if show_command:
        logging.basicConfig(level=logging.INFO)

    tmux_command = hs.Command("tmux")
    tmux_command.bake(
        "-L",
        server_name,
        "list-sessions",
        "-F",
        '"#{session_created} #{session_name}: #{session_windows} windows (created #{t:session_created})#{?session_grouped, (group ,}#{session_group}#{?session_grouped,),} #{pane_title} #{?session_attached,(attached),}"',
    )
    if only_detached:
        tmux_command.bake("-f", "#{==:#{session_attached},0}")
    elif only_attached:
        tmux_command.bake("-f", "#{session_attached}")

    _results = tmux_command().strip().split("\n")

    for _result in _results:
        ic(_result)
        yield _result


def get_server_pids():
    server_pids = []
    for proc in psutil.process_iter(["pid", "name", "username", "open_files"]):
        if proc.info["name"] == "tmux: server":
            server_pids.append(proc.info["pid"])

    return server_pids


def get_server_sockets():
    server_pids = get_server_pids()
    sockets = set()
    for conn in psutil.net_connections(kind="unix"):
        if conn.pid in server_pids:
            if conn.laddr.startswith(f"/tmp/tmux-{os.getuid()}/"):
                sockets.add(conn.laddr)
    return sockets


def get_tmux_server_names():
    server_sockets = get_server_sockets()
    ic(server_sockets)
    for socket in server_sockets:
        yield Path(socket).name


@click.group(no_args_is_help=True, cls=AHGroup)
@click_add_options(click_global_options)
@click.pass_context
def cli(
    ctx,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )


@cli.command()
@click.argument("server_name", type=str)
@click.argument(
    "arguments",
    type=str,
    nargs=-1,
)
@click_add_options(click_global_options)
@click.pass_context
def run(
    ctx,
    server_name: str,
    arguments: tuple[str, ...],
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    launch_tmux(
        server_name=server_name,
        arguments=arguments,
    )


@cli.command("in-tmux")
@click_add_options(click_global_options)
@click.pass_context
def _in_tmux(
    ctx,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    try:
        in_tmux()
    except ValueError:
        eprint("Error: not in tmux")
        sys.exit(1)


@cli.command("list")
@click.argument(
    "server_names",
    type=str,
    nargs=-1,
)
@click.option("--detached", is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def alias_list_ls(
    ctx,
    server_names: tuple[str, ...],
    detached: bool,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    ctx.invoke(
        ls,
        server_names=server_names,
        verbose=verbose,
        verbose_inf=verbose_inf,
        detached=detached,
    )


def list_all_sessions(
    *,
    servers: None | tuple[str, ...],
    only_detached: bool,
):
    if not servers:
        servers = get_tmux_server_names()
    for index, server in enumerate(servers):
        ic(index, server)
        for line in list_tmux(
            server_name=server,
            show_command=False,
            only_detached=only_detached,
            only_attached=False,
        ):
            yield server, line


@cli.command()
@click.argument(
    "server_names",
    type=str,
    nargs=-1,
)
@click.option("--detached", is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def ls(
    ctx,
    server_names: tuple[str, ...],
    detached: bool,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    if server_names:
        iterator = server_names
    else:
        iterator = get_tmux_server_names()

    for server, line in list_all_sessions(
        servers=iterator,
        only_detached=False,
    ):
        output(
            (server, line),
            reason=server,
            dict_output=dict_output,
            tty=tty,
        )


@cli.command()
@click.argument(
    "server_names",
    type=str,
    nargs=-1,
)
@click.option("--reverse", is_flag=True)
@click.option("--simulate", is_flag=True)
@click.option(
    "--all",
    "all_at_once",
    is_flag=True,
)
@click_add_options(click_global_options)
@click.pass_context
def attach(
    ctx,
    server_names: tuple[str, ...],
    verbose_inf: bool,
    dict_output: bool,
    reverse: bool,
    simulate: bool,
    all_at_once: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    if server_names:
        iterator = server_names
    else:
        iterator = get_tmux_server_names()

    _iterator = list(iterator)
    ic(_iterator)

    if reverse:
        _iterator = list(reversed(_iterator))
        ic(_iterator)
        _ = input("press enter")

    for index, server in enumerate(_iterator):
        ic(index, server)
        for line in list_tmux(
            server_name=server,
            show_command=False,
            only_detached=True,
            only_attached=False,
        ):
            ic(line)
            if not line.endswith("(attached)"):
                window_id = line.split(":")[0].split(" ")[-1]
                command = f"tmux -L {server} attach -t {window_id}"
                if all_at_once:
                    command = "/usr/bin/xterm -e '" + command + "'"
                    command += " &"
                if ic.enabled:
                    eprint("attaching:", command)
                if not simulate:
                    os.system(command)


@cli.command()
@click.argument(
    "prefix",
    type=str,
    nargs=1,
)
@click.option("--reverse", is_flag=True)
@click.option("--simulate", is_flag=True)
@click.option(
    "--all",
    "all_at_once",
    is_flag=True,
)
@click_add_options(click_global_options)
@click.pass_context
def attach_prefix(
    ctx,
    prefix: str,
    verbose_inf: bool,
    dict_output: bool,
    reverse: bool,
    simulate: bool,
    all_at_once: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    for server, line in list_all_sessions(servers=None, only_detached=True):
        if not server.startswith(prefix):
            continue
        if not line:
            continue
        icp(server, line)

        if not line.endswith("(attached)"):
            window_id = line.split(":")[0].split(" ")[-1]
            command = f"tmux -L {server} attach -t {window_id}"
            if all_at_once:
                command = "/usr/bin/xterm -e '" + command + "'"
                command += " &"
            if ic.enabled:
                eprint("attaching:", command)
            if not simulate:
                os.system(command)
