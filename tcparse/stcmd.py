"""
"tcparse-stcmd" is a command line utility for generating ESS/ethercatmc-capable
EPICS startup st.cmd files directly from TwinCAT3 .tsproj projects.

Relies on the existence (and linking) of FB_DriveVirtual function blocks.
"""

import argparse
import logging

from .parse import load_project, Symbol_FB_DriveVirtual


description = __doc__


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        'tsproj_project', type=str,
        help='Path to .tsproj project'
    )

    parser.add_argument(
        '--log',
        '-l',
        default='WARNING',  # WARN level messages
        type=str,
        help='Python logging level (e.g. DEBUG, INFO, WARNING)'
    )

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    logger = logging.getLogger('tcparse')
    logger.setLevel(args.log)

    project = load_project(args.tsproj_project)
    motors = list(project.find(Symbol_FB_DriveVirtual))
    for motor in motors:
        print(motor)


if __name__ == '__main__':
    main()
