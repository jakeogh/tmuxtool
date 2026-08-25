#!/usr/bin/env python3

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
from clicktool import tvic
from eprint import eprint

signal(SIGPIPE, SIG_DFL)

_tmux = hs.Command("tmux")


def in_tmux() -> None:
    try:
        print("os.environ['TMUX']:", os.environ["TMUX"])
    except KeyError:
        raise ValueError("start tmux!")


class MultiPaneSession:
    # manage a tmux session with multiple panes:
    #   with MultiPaneSession("myserver", "mysession", layout="tiled") as session:
    #       session.add_pane("/usr/bin/greendb", "-c", "config.json", title="db1")
    def __init__(
        self,
        server_name: str,
        session_name: str,
        layout: str = "tiled",
        force_new: bool = False,
    ):
        self.server_name = server_name
        self.session_name = session_name
        self.layout = layout
        self.current_window: None | str = None
        self.pane_count = 0

        _tmux("-L", server_name, "start-server")

        if force_new:
            try:
                _tmux("-L", server_name, "kill-session", "-t", session_name)
            except hs.ErrorReturnCode:
                pass  # session didn't exist

        try:
            _tmux("-L", server_name, "has-session", "-t", session_name)
        except hs.ErrorReturnCode:
            _tmux(
                "-L",
                server_name,
                "new-session",
                "-d",
                "-s",
                session_name,
                "sleep",
                "infinity",  # placeholder, replaced by first add_pane
            )

        _tmux(
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
        return str(
            self._tmux(
                "display-message",
                "-t",
                self.session_name,
                "-p",
                "#{window_id}",
            )
        ).strip()

    def _tmux(self, *args):
        return _tmux("-L", self.server_name, *args)

    def add_pane(
        self,
        *command: str,
        title: None | str = None,
        window: None | str = None,
    ) -> str:
        if not command:
            raise ValueError("Command cannot be empty")

        if window is None:
            window = title or f"win-{self.pane_count}"

        if self.pane_count == 0:
            # first command replaces the placeholder pane
            target = f"{self.session_name}:{self.current_window}.0"
            self._tmux("respawn-pane", "-t", target, "-k", *command)
            window_id = str(
                self._tmux("display-message", "-t", target, "-p", "#{window_id}")
            ).strip()
            if title is not None:
                self._tmux("rename-window", "-t", window_id, title)
        else:
            window_id = str(
                self._tmux(
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
                )
            ).strip()

        self.pane_count += 1
        return window_id

    def new_window(self, name: str) -> str:
        window_id = str(
            self._tmux(
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
                "infinity",  # placeholder for first pane
            )
        ).strip()

        self.current_window = name
        self.pane_count = 0

        return window_id

    def apply_layout(self, layout: None | str = None) -> None:
        layout_to_use = layout if layout is not None else self.layout

        try:
            self._tmux(
                "select-layout",
                "-t",
                f"{self.session_name}:{self.current_window}",
                layout_to_use,
            )
        except hs.ErrorReturnCode as e:
            # layout can fail with certain pane counts, that's OK
            ic(f"Layout application failed (might be OK): {e}")

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):
        self.apply_layout()
        return False


def launch_tmux(
    *,
    server_name: str,
    arguments: list | tuple,
) -> None:
    assert isinstance(arguments, (list, tuple))
    _tmux("-L", server_name, "start-server")
    _tmux(
        "-L",
        server_name,
        "set-option",
        "-g",
        "remain-on-exit",
        "failed",
    )

    xterm_command = hs.Command("xterm").rebake(
        "-e",
        "tmux",
        "-L",
        server_name,
        "new-session",
        "-d",
        *arguments,
    )
    ic(xterm_command)
    xterm_command(_bg=True, _bg_exc=True)


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

    _results = str(tmux_command()).strip().split("\n")

    for _result in _results:
        ic(_result)
        yield _result


def get_server_pids() -> list[int]:
    server_pids = []
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] == "tmux: server":
            server_pids.append(proc.info["pid"])

    return server_pids


def get_server_sockets() -> set[str]:
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


def _attach_session(
    *,
    server: str,
    line: str,
    all_at_once: bool,
    simulate: bool,
) -> None:
    if line.endswith("(attached)"):
        return
    session_target = line.split(":")[0].split(" ")[-1]
    attach_args = ("-L", server, "attach", "-t", session_target)
    if ic.enabled:
        eprint("attaching: tmux", " ".join(attach_args))
    if simulate:
        return
    if all_at_once:
        # a user closing the attach xterm is not an error
        hs.Command("/usr/bin/xterm")(
            "-e",
            "tmux",
            *attach_args,
            _bg=True,
            _bg_exc=False,
        )
    else:
        _tmux(*attach_args, _fg=True)


@click.group(no_args_is_help=True, cls=AHGroup)
@click_add_options(click_global_options)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:
    tty, verbose = tvic(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
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
    ctx: click.Context,
    server_name: str,
    arguments: tuple[str, ...],
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:
    tty, verbose = tvic(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
    )

    launch_tmux(
        server_name=server_name,
        arguments=arguments,
    )


@cli.command("in-tmux")
@click_add_options(click_global_options)
@click.pass_context
def _in_tmux(
    ctx: click.Context,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:
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
    ctx: click.Context,
    server_names: tuple[str, ...],
    detached: bool,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:
    ctx.invoke(
        ls,
        server_names=server_names,
        verbose=verbose,
        verbose_inf=verbose_inf,
        detached=detached,
    )


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
    ctx: click.Context,
    server_names: tuple[str, ...],
    detached: bool,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:
    tty, verbose = tvic(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
    )

    if server_names:
        iterator = server_names
    else:
        iterator = get_tmux_server_names()

    for server, line in list_all_sessions(
        servers=iterator,
        only_detached=detached,
    ):
        print({server: (server, line)} if dict_output else (server, line), flush=True)


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
    ctx: click.Context,
    server_names: tuple[str, ...],
    verbose_inf: bool,
    dict_output: bool,
    reverse: bool,
    simulate: bool,
    all_at_once: bool,
    verbose: bool = False,
) -> None:
    tty, verbose = tvic(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
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

    for index, server in enumerate(_iterator):
        ic(index, server)
        for line in list_tmux(
            server_name=server,
            show_command=False,
            only_detached=True,
            only_attached=False,
        ):
            ic(line)
            _attach_session(
                server=server,
                line=line,
                all_at_once=all_at_once,
                simulate=simulate,
            )


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
    ctx: click.Context,
    prefix: str,
    verbose_inf: bool,
    dict_output: bool,
    reverse: bool,
    simulate: bool,
    all_at_once: bool,
    verbose: bool = False,
) -> None:
    tty, verbose = tvic(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
    )

    for server, line in list_all_sessions(servers=None, only_detached=True):
        if not server.startswith(prefix):
            continue
        if not line:
            continue
        icp(server, line)
        _attach_session(
            server=server,
            line=line,
            all_at_once=all_at_once,
            simulate=simulate,
        )
