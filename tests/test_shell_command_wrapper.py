from plumbum import local
from plumbum.cmd import ls
from teff_py.shell_command_wrapper import ShellCommandWrapperBase

def test_shell_command_wrapper_base_execution():
    # Assuming `ls` command is available everywhere.
    ls_wrap = ShellCommandWrapperBase(ls, ["-lt"])

    ls_wrap.add_arg("-a")
    ls_wrap.add_arg("/tmp")

    success, message = ls_wrap.run()
    assert(success is True)
    assert(ls_wrap._exit_code == 0)
    assert(len(ls_wrap._out_log) > 0)

    # successful execution of an instance is forbidden
    success2, message2 = ls_wrap.run()
    assert(success2 is False)
