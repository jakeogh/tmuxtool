#!/usr/bin/env python3
# -*- coding: utf8 -*-
# tab-width:4

# pylint: disable=C0111  # docstrings are always outdated and wrong
# pylint: disable=C0114  # Missing module docstring (missing-module-docstring)
# pylint: disable=W0511  # todo is encouraged
# pylint: disable=C0301  # line too long
# pylint: disable=R0902  # too many instance attributes
# pylint: disable=C0302  # too many lines in module
# pylint: disable=C0103  # single letter var names, func name too descriptive
# pylint: disable=R0911  # too many return statements
# pylint: disable=R0912  # too many branches
# pylint: disable=R0915  # too many statements
# pylint: disable=R0913  # too many arguments
# pylint: disable=R1702  # too many nested blocks
# pylint: disable=R0914  # too many local variables
# pylint: disable=R0903  # too few public methods
# pylint: disable=E1101  # no member for base
# pylint: disable=W0201  # attribute defined outside __init__
# pylint: disable=R0916  # Too many boolean expressions in if statement
# pylint: disable=C0305  # Trailing newlines editor should fix automatically, pointless warning

import os
from math import inf
from pathlib import Path
from signal import SIG_DFL
from signal import SIGPIPE
from signal import signal
from typing import Union

import click
import psutil
import sh
from asserttool import ic
from click_auto_help import AHGroup
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tv
from mptool import output
from mptool import unmp

sh.mv = None  # use sh.busybox('mv'), coreutils ignores stdin read errors

signal(SIGPIPE, SIG_DFL)


def launch_tmux(*,
                server_name: str,
                arguments: Union[list, tuple],
                verbose: Union[bool, int, float],
                ):

    sh.tmux('-L', server_name, 'start-server')
    sh.tmux('-L', server_name, 'set-option', '-g', 'remain-on-exit', 'failed')

    xterm_process = sh.xterm.bake('-e',
                                  'tmux',
                                  '-L',
                                  server_name,
                                  'new-session',
                                  '-d', *arguments,)

    if verbose:
        ic(xterm_process)

    xterm_process(_bg=True, _bg_exc=True)


def list_tmux(*,
              server_name: str,
              verbose: Union[bool, int, float],
              ):

    if verbose:
        ic(server_name)
    for line in sh.tmux('-L', server_name, 'ls'):
        if verbose:
            ic(line)
        yield line


def get_server_pids():
    server_pids = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'open_files']):
        if proc.info['name'] == 'tmux: server':
            server_pids.append(proc.info['pid'])

    return server_pids


def get_server_sockets():
    server_pids = get_server_pids()
    sockets = set([])
    for conn in psutil.net_connections(kind='unix'):
        #ic(conn)
        if conn.pid in server_pids:
            if conn.laddr.startswith(f"/tmp/tmux-{os.getuid()}/"):
                #ic(conn)
                sockets.add(conn.laddr)
    return sockets


def get_tmux_server_names(verbose: Union[bool, int, float]):
    server_sockets = get_server_sockets()
    if verbose:
        ic(server_sockets)
    for socket in server_sockets:
        yield Path(socket).name


@click.group(no_args_is_help=True, cls=AHGroup)
@click_add_options(click_global_options)
@click.pass_context
def cli(ctx,
        verbose: Union[bool, int, float],
        verbose_inf: bool,
        ):

    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )


@cli.command()
@click.argument('server_name', type=str)
@click.argument("arguments", type=str, nargs=-1)
@click_add_options(click_global_options)
@click.pass_context
def run(ctx,
        server_name: str,
        arguments: tuple[str],
        verbose: Union[bool, int, float],
        verbose_inf: bool,
        ):

    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    launch_tmux(server_name=server_name,
                arguments=arguments,
                verbose=verbose,)


@cli.command('list')
@click.argument('server_names', type=str, nargs=-1)
@click_add_options(click_global_options)
@click.pass_context
def alias_list_ls(ctx,
                  server_names: tuple[str],
                  verbose: Union[bool, int, float],
                  verbose_inf: bool,
                  ):

    ctx.invoke(ls, server_names=server_names, verbose=verbose, verbose_inf=verbose_inf)


@cli.command()
@click.argument('server_names', type=str, nargs=-1)
@click_add_options(click_global_options)
@click.pass_context
def ls(ctx,
       server_names: tuple[str],
       verbose: Union[bool, int, float],
       verbose_inf: bool,
       ):

    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    if server_names:
        iterator = server_names
    else:
        iterator = get_tmux_server_names(verbose=verbose)

    for index, server in enumerate(iterator):
        if verbose:
            ic(index, server)
        for line in list_tmux(server_name=server,
                              verbose=verbose,):
            output((server, line), tty=tty, verbose=verbose)


@cli.command()
@click.argument('server_names', type=str, nargs=-1)
@click_add_options(click_global_options)
@click.pass_context
def attach(ctx,
           server_names: tuple[str],
           verbose: Union[bool, int, float],
           verbose_inf: bool,
           ):

    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    if server_names:
        iterator = server_names
    else:
        iterator = get_tmux_server_names(verbose=verbose)

    for index, server in enumerate(iterator):
        if verbose:
            ic(index, server)
        for line in list_tmux(server_name=server,
                              verbose=verbose,):
            if verbose == inf:
                ic(line)
            if not line.endswith('(attached)\n'):
                window_id = line.split(':')[0]
                #ic(window_id)
                os.system(f'tmux -L {server} attach -t {window_id}')
