from ..stcmd import main as stcmd_main


def test_stcmd(project_filename):
    stcmd_main(cmdline_args=[project_filename])
