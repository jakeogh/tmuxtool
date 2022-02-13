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
import subprocess
from pathlib import Path
from signal import SIG_DFL
from signal import SIGPIPE
from signal import signal
from typing import Union

import click
import psutil
import sh
from asserttool import ic
from asserttool import tv
from click_auto_help import AHGroup
from clicktool import click_add_options
from clicktool import click_global_options

sh.mv = None  # use sh.busybox('mv'), coreutils ignores stdin read errors

signal(SIGPIPE, SIG_DFL)


def launch_tmux(*,
                server_name: str,
                arguments: Union[list, tuple],
                verbose: int,
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
              verbose: int,
              ):

    for line in sh.tmux('-L', server_name, 'ls'):
        ic(line)

    #sh.tmux('-L', server_name, 'set-option', '-g', 'remain-on-exit', 'failed')

    #xterm_process = sh.xterm.bake('-e',
    #                              'tmux',
    #                              '-L',
    #                              server_name,
    #                              'new-session',
    #                              '-d', *arguments,)

    #if verbose:
    #    ic(xterm_process)

    #xterm_process(_bg=True, _bg_exc=True)


def get_server_pids():
    server_pids = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'open_files']):
        if proc.info['name'].startswith('tmux'):
            print(proc.info)
            server_pids.append(proc.info['pid'])

    return server_pids


def get_server_sockets():
    server_pids = get_server_pids()
    for conn in psutil.net_connections(kind='unix'):
        ic(conn)
        if conn.pid in server_pids:
            ic(conn)


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
        verbose: int,
        verbose_inf: bool,
        ):

    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    launch_tmux(server_name=server_name,
                arguments=arguments,
                verbose=verbose,)


@cli.command()
@click.argument('server_name', type=str)
@click_add_options(click_global_options)
@click.pass_context
def ls(ctx,
       server_name: str,
       verbose: int,
       verbose_inf: bool,
       ):

    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    list_tmux(server_name=server_name,
              verbose=verbose,)

    get_server_sockets()
