from ..stcmd import main as stcmd_main


def test_stcmd(project_filename):
    print(stcmd_main(cmdline_args=[project_filename]))
