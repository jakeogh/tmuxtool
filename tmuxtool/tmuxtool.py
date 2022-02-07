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
# pylint: disable=C0413  # TEMP isort issue [wrong-import-position] Import "from pathlib import Path" should be placed at the top of the module [C0413]

# code style:
#   no guessing on spelling: never tmp_X always temporary_X
#   dont_makedirs -> no_makedirs
#   no guessing on case: local vars, functions and methods are lower case. classes are ThisClass(). Globals are THIS.
#   del vars explicitely ASAP, assumptions are buggy
#   rely on the compiler, code verbosity and explicitness can only be overruled by benchamrks (are really compiler bugs)
#   no tabs. code must display the same independent of viewer
#   no recursion, recursion is undecidiable, randomly bounded, and hard to reason about
#   each elementis the same, no special cases for the first or last elemetnt:
#       [1, 2, 3,] not [1, 2, 3]
#       def this(*.
#                a: bool,
#                b: bool,
#               ):
#
#   expicit loop control is better than while (condition):
#       while True:
#           # continue/break explicit logic


# TODO:
#   https://github.com/kvesteri/validators
import os
import sys
import click
import time
import sh
from clicktool import click_add_options, click_global_options
from signal import signal, SIGPIPE, SIG_DFL
from pathlib import Path
#from with_sshfs import sshfs
#from with_chdir import chdir
from printtool import output
from asserttool import tv
from asserttool import validate_slice
from asserttool import eprint, ic
from retry_on_exception import retry_on_exception
from enumerate_input import enumerate_input
#from collections import defaultdict
#from prettyprinter import cpprint
#from prettyprinter import install_extras
#install_extras(['attrs'])
from timetool import get_timestamp
#from configtool import click_read_config
#from configtool import click_write_config_entry

#from asserttool import not_root
#from pathtool import path_is_block_special
#from pathtool import write_line_to_file
#from getdents import files
#from prettytable import PrettyTable
#output_table = PrettyTable()

from unmp import unmp
from typing import List
from typing import Tuple
from typing import Sequence
from typing import Generator
from typing import Iterable
from typing import ByteString
from typing import Optional
from typing import Union

sh.mv = None  # use sh.busybox('mv'), coreutils ignores stdin read errors

# click-command-tree
#from click_plugins import with_plugins
#from pkg_resources import iter_entry_points

# import pdb; pdb.set_trace()
# #set_trace(term_size=(80, 24))
# from pudb import set_trace; set_trace(paused=False)

##def log_uncaught_exceptions(ex_cls, ex, tb):
##   eprint(''.join(traceback.format_tb(tb)))
##   eprint('{0}: {1}'.format(ex_cls, ex))
##
##sys.excepthook = log_uncaught_exceptions

#this should be earlier in the imports, but isort stops working
signal(SIGPIPE, SIG_DFL)

#@with_plugins(iter_entry_points('click_command_tree'))
#@click.group()
#@click_add_options(click_global_options)
#@click.pass_context
#def cli(ctx,
#        verbose: int,
#        verbose_inf: bool,
#        ):
#
#    tty, verbose = tv(ctx=ctx,
#                      verbose=verbose,
#                      verbose_inf=verbose_inf,
#                      )


# update setup.py if changing function name
#@click.argument("slice_syntax", type=validate_slice, nargs=1)
@click.command()
@click.argument("paths", type=str, nargs=-1)
@click.argument("sysskel",
                type=click.Path(exists=False,
                                dir_okay=True,
                                file_okay=False,
                                allow_dash=False,
                                path_type=Path,),
                nargs=1,
                required=True,)
@click.option('--ipython', is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def cli(ctx,
        paths: Optional[tuple[str]],
        sysskel: Path,
        ipython: bool,
        verbose: int,
        verbose_inf: bool,
        ):

    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    if paths:
        iterator = paths
    else:
        iterator = unmp(valid_types=[bytes,], verbose=verbose)
    del paths

    index = 0
    for index, path in enumerate(iterator):
        path = Path(os.fsdecode(path))

        if verbose:  # or simulate:
            ic(index, path)
        #if count:
        #    if count > (index + 1):
        #        ic(count)
        #        sys.exit(0)

        #if simulate:
        #    continue

        with open(path, 'rb') as fh:
            path_bytes_data = fh.read()

        if not count:
            output(path, tty=tty, verbose=verbose)

    if count:
        output(index + 1, tty=tty, verbose=verbose)

#        if ipython:
#            import IPython; IPython.embed()



#!/usr/bin/env python3

import sys
from pathlib import Path
import sh
import msgpack
import logging
from icecream import ic
from clipboardtool import get_clipboard_iris
from with_lmdb import LmdbEnviroment, LmdbTransaction, LmdbZset
from menu import menu


#def get_greendb_values(path: Path,):
#    _tags = []
#    with LmdbEnviroment(path=path,
#                        write=False,
#                        writemap=False,
#                        readahead=True,
#                        duplicate_keys=False,
#                        tmpfs=False,
#                        max_dbs=1,
#                        verbose=False,
#                        ) as env:
#        subdb = env.open_db(b'db0')
#        with LmdbTransaction(env=env,
#                             write=False,
#                             verbose=False,
#                             ) as txn:  # https://lmdb.readthedocs.io/en/release/#lmdb.Transaction
#            cursor = txn.cursor(db=subdb)
#            iterator = cursor.iternext(keys=False)
#            for tag in iterator:
#                tag_unpacked = msgpack.unpackb(tag, raw=False)
#                _tags.append(tag_unpacked)
#    return _tags


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    iris = list(get_clipboard_iris())

    depth = int(sys.argv[1])
    ic(iris, depth)

    video_plugin = False
    if depth < 0:
        video_plugin = True
    depth = abs(depth)

    if len(sys.argv) == 1:
        depth = int(sys.argv[1])
    if len(sys.argv) > 2:
        raise ValueError('too many arguments', sys.argv)

    tags = []

    #cache_file = Path('/poolz1_2x4TB_B/iridb/cache/file/tags/tags.messagepack')
    #if cache_file.exists():
    #    with open(cache_file, 'rb') as fh:
    #        data = fh.read()
    #        tags = msgpack.packb(data, use_bin_type=True)
    #        #tags = [_.strip() for _ in fh.readlines()]

    zset = LmdbZset(verbose=False,)
    if not tags:  # cache was empty?
        #tags = get_tags_zset_list()
        tags = list(zset)

    for tag in tags:
        assert isinstance(tag, bytes)

    tag = menu(iterator=tags,
               msg="enter tag:",
               verbose=False,
               )

    for iri in iris:
        ic(tag, iri, depth)
        sh.tmux('-L', 'iridbjob', 'start-server')
        sh.tmux('-L', 'iridbjob', 'set-option', '-g', 'remain-on-exit', 'failed')
                                      #'-f',
                                      #'/dev/null',
                                      #'-N',

        xterm_process = sh.xterm.bake('-e',
                                      'tmux',
                                      '-L',
                                      'iridbjob',
                                      'new-session',
                                      '-d', '/usr/bin/iridb', 'spider', iri, '--depth', depth, '--tag', tag,)
        if video_plugin:
            xterm_process.bake('--enable-video-plugin')

        ic(xterm_process)
        xterm_process(_bg=True, _bg_exc=True)

        zset.add(tag.encode('utf8'), update_existing=True)
