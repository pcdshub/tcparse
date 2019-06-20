"""
"tcparse-summary" is a command line utility for inspecting TwinCAT3
.tsproj projects.
"""

import argparse
import logging

from .parse import load_project, Property


DESCRIPTION = __doc__


def build_arg_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser(
            description=DESCRIPTION,
            formatter_class=argparse.RawTextHelpFormatter
        )

    parser.add_argument(
        'tsproj_project', type=str,
        help='Path to .tsproj project'
    )

    parser.add_argument(
        '--log',
        '-l',
        default='INFO',
        type=str,
        help='Python logging level (e.g. DEBUG, INFO, WARNING)'
    )

    return parser


def _summary(project):
    print('summary', project)


def summary(args):
    logger = logging.getLogger('tcparse')
    logger.setLevel(args.log)
    logging.basicConfig()

    project = load_project(args.tsproj_project)
    _summary(project)
    return project


def main(*, cmdline_args=None):
    parser = build_arg_parser()
    args = parser.parse_args(cmdline_args)
    return summary(args)
