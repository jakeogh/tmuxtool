#!/usr/bin/env python3
# -*- coding: utf8 -*-

# pylint: disable=missing-docstring               # [C0111] docstrings are always outdated and wrong
# pylint: disable=missing-module-docstring        # [C0114]
# pylint: disable=fixme                           # [W0511] todo is encouraged
# pylint: disable=line-too-long                   # [C0301]
# pylint: disable=too-many-instance-attributes    # [R0902]
# pylint: disable=too-many-lines                  # [C0302] too many lines in module
# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive
# pylint: disable=too-many-return-statements      # [R0911]
# pylint: disable=too-many-branches               # [R0912]
# pylint: disable=too-many-statements             # [R0915]
# pylint: disable=too-many-arguments              # [R0913]
# pylint: disable=too-many-nested-blocks          # [R1702]
# pylint: disable=too-many-locals                 # [R0914]
# pylint: disable=too-few-public-methods          # [R0903]
# pylint: disable=no-member                       # [E1101] no member for base
# pylint: disable=attribute-defined-outside-init  # [W0201]
# pylint: disable=too-many-boolean-expressions    # [R0916] in if statement

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from signal import SIG_DFL
from signal import SIGPIPE
from signal import signal

import click
import psutil
import sh
from asserttool import ic
from click_auto_help import AHGroup
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tvicgvd
from eprint import eprint
from globalverbose import gvd
from mptool import output

sh.mv = None  # use sh.busybox('mv'), coreutils ignores stdin read errors

signal(SIGPIPE, SIG_DFL)

logging.basicConfig(level=logging.INFO)


def in_tmux(
    verbose: bool = False,
):
    try:
        print("os.environ['TMUX']:", os.environ["TMUX"])
    except KeyError:
        raise ValueError("start tmux!")
        # print("start tmux!", file=sys.stderr)
        # sys.exit(1)


def launch_tmux(
    *,
    server_name: str,
    arguments: list | tuple,
    verbose: bool = False,
):
    assert isinstance(arguments, list) or isinstance(arguments, tuple)
    sh.tmux("-L", server_name, "start-server")
    sh.tmux("-L", server_name, "set-option", "-g", "remain-on-exit", "failed")

    xterm_process = sh.xterm.bake(
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
    verbose: bool = False,
):
    ic(server_name)
    # tmux_command = sh.Command('tmux')
    # tmux_command.bake('-L', server_name, 'ls')
    # if show_command:
    #    tmux_command.bake('-F', '"#{session_created} #{session_name}: #{session_windows} windows (created #{t:session_created})#{?session_grouped, (group ,}#{session_group}#{?session_grouped,),} #{pane_title} #{?session_attached,(attached),}"')

    # -f "#{session_attached}"

    tmux_command = sh.Command("tmux")
    tmux_command = tmux_command.bake(
        "-L",
        server_name,
        "list-sessions",
        "-F",
        '"#{session_created} #{session_name}: #{session_windows} windows (created #{t:session_created})#{?session_grouped, (group ,}#{session_group}#{?session_grouped,),} #{pane_title} #{?session_attached,(attached),}"',
    )
    if only_detached:
        tmux_command = tmux_command.bake("-f", '"#{session_attached}"')

    _results = tmux_command().strip().split("\n")

    # _results = (
    #    sh.tmux(
    #        "-L",
    #        server_name,
    #        "list-sessions",
    #        "-F",
    #        '"#{session_created} #{session_name}: #{session_windows} windows (created #{t:session_created})#{?session_grouped, (group ,}#{session_group}#{?session_grouped,),} #{pane_title} #{?session_attached,(attached),}"',
    #    )
    #    .strip()
    #    .split("\n")
    # )
    for _result in _results:
        ic(_result)
        yield _result
    # else:
    #    for line in sh.tmux("-L", server_name, "ls").strip().split("\n"):
    #        ic(line)
    #        yield line


def get_server_pids():
    server_pids = []
    for proc in psutil.process_iter(["pid", "name", "username", "open_files"]):
        if proc.info["name"] == "tmux: server":
            server_pids.append(proc.info["pid"])

    return server_pids


def get_server_sockets():
    server_pids = get_server_pids()
    sockets = set([])
    for conn in psutil.net_connections(kind="unix"):
        # ic(conn)
        if conn.pid in server_pids:
            if conn.laddr.startswith(f"/tmp/tmux-{os.getuid()}/"):
                # ic(conn)
                sockets.add(conn.laddr)
    return sockets


def get_tmux_server_names(verbose: bool | int | float = False):
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
@click.argument("arguments", type=str, nargs=-1)
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
@click.argument("server_names", type=str, nargs=-1)
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


@cli.command()
@click.argument("server_names", type=str, nargs=-1)
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

    for index, server in enumerate(iterator):
        ic(index, server)
        for line in list_tmux(
            server_name=server,
            show_command=tty,
            only_detached=detached,
        ):
            output(
                (server, line),
                reason=server,
                dict_output=dict_output,
                tty=tty,
            )


@cli.command()
@click.argument("server_names", type=str, nargs=-1)
@click.option("--reverse", is_flag=True)
@click.option("--simulate", is_flag=True)
@click.option("--all", "all_at_once", is_flag=True)
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
        _iterator = reversed(_iterator)
        ic(_iterator)
        _ = input("press enter")

    for index, server in enumerate(_iterator):
        ic(index, server)
        for line in list_tmux(
            server_name=server,
            show_command=False,
            only_detached=True,
        ):
            ic(line)
            if not line.endswith("(attached)"):
                window_id = line.split(":")[0]
                # ic(window_id)
                command = f"tmux -L {server} attach -t {window_id}"
                if all_at_once:
                    command = "/usr/bin/xterm -e '" + command + "'"
                    command += " &"
                if ic.enabled:
                    eprint("attaching:", command)
                if not simulate:
                    os.system(command)
