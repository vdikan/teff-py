from plumbum import local
from teff_py.actions import ActionLocal, State

class Parent():             # mock parent class
    path = "/tmp"

def test_local_action():
    class TempAction(ActionLocal):
        command = local["ls"]
        
    ls = TempAction(["-a", "./"], parent=Parent())
    ls.prepare()
    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rmdir"](ls.path)     # cleanup


def test_local_action_mpi():
    class TempAction(ActionLocal):
        num_mpi_procs = 2
        command = local["ls"]
    
    ls = TempAction(["-a", "./"], parent=Parent())
    ls.prepare()
    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rmdir"](ls.path)     # cleanup


def test_bound_action():
    class TempAction(ActionLocal):
        parent_path = "/tmp"
        command = local["ls"]["-l"]
    
    ls = TempAction(["-a", "./"], parent=Parent())
    ls.prepare()
    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rmdir"](ls.path)     # cleanup


def test_bound_action_mpi():
    class TempAction(ActionLocal):
        num_mpi_procs = 2
        command = local["ls"]["-l"]
    
    ls = TempAction(["-a", "./"], parent=Parent())
    ls.prepare()
    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rmdir"](ls.path)     # cleanup
