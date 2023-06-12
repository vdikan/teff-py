from plumbum import local
from teff_py.actions import Action, State

class Parent():             # mock parent class
    path = local.path("/tmp")
    
    def make_prefix(self):
        return "mock_parent"

def test_local_action():
    class TempAction(Action):
        command = local["ls"]
        
    ls = TempAction(["-a", "./"], parent=Parent())
    ls.prepare()
    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rm"]("-r", ls.path)     # cleanup


def test_local_action_mpi():
    class TempAction(Action):
        num_mpi_procs = 2
        command = local["ls"]
    
    ls = TempAction(["-a", "./"], parent=Parent())
    ls.prepare()
    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rm"]("-r", ls.path)     # cleanup


def test_bound_action():
    class TempAction(Action):
        parent_path = "/tmp"
        command = local["ls"]["-l"]
    
    ls = TempAction(["-a", "./"], parent=Parent())
    ls.prepare()
    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rm"]("-r", ls.path)     # cleanup


def test_bound_action_mpi():
    class TempAction(Action):
        num_mpi_procs = 2
        command = local["ls"]["-l"]
    
    ls = TempAction(["-a", "./"], parent=Parent())
    ls.prepare()
    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rm"]("-r", ls.path)     # cleanup
