"""
`tcparse` is the top-level command for accessing tcparse-stcmd and
tcparse-summary.

Try::

    $ tcparse stcmd --help
    $ tcparse summary --help
"""

import argparse

from .summary import (build_arg_parser as build_summary_arg_parser,
                      summary as summary_main)
from .stcmd import (build_arg_parser as build_stcmd_arg_parser,
                    render as render_stcmd)


DESCRIPTION = __doc__


def stcmd_main(args):
    _, _, template = render_stcmd(args)
    print(template)


COMMANDS = {
    'stcmd': (build_stcmd_arg_parser, stcmd_main),
    'summary': (build_summary_arg_parser, summary_main),
}


def main():
    top_parser = argparse.ArgumentParser(
        prog='tcparse',
        description=DESCRIPTION,
        formatter_class=argparse.RawTextHelpFormatter
    )

    top_parser.add_argument(
        '--log',
        '-l',
        default='INFO',
        type=str,
        help='Python logging level (e.g. DEBUG, INFO, WARNING)'
    )

    subparsers = top_parser.add_subparsers(help='Possible subcommands')
    for command_name, (build_func, main) in COMMANDS.items():
        sub = subparsers.add_parser(command_name)
        build_func(sub)
        sub.set_defaults(func=main)

    args = top_parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        top_parser.print_help()
