from plumbum import local
from teff_py.actions import ActionDefault, State

def test_local_action():
    class TempAction(ActionDefault):
        parent_path = "/tmp"
        command = local["ls"]
    
    ls = TempAction(["-a", "./"])
    ls.prepare()

    print(ls.runner.args)

    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rmdir"](ls.path)     # cleanup


def test_local_action_mpi():
    class TempAction(ActionDefault):
        parent_path = "/tmp"
        num_mpi_procs = 2
        command = local["ls"]
    
    ls = TempAction(["-a", "./"])
    ls.prepare()

    print(ls.runner.args)

    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rmdir"](ls.path)     # cleanup


def test_bound_action():
    class TempAction(ActionDefault):
        parent_path = "/tmp"
        command = local["ls"]["-l"]
    
    ls = TempAction(["-a", "./"])
    ls.prepare()

    print(ls.runner.args)

    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rmdir"](ls.path)     # cleanup


def test_bound_action_mpi():
    class TempAction(ActionDefault):
        parent_path = "/tmp"
        num_mpi_procs = 2
        command = local["ls"]["-l"]
    
    ls = TempAction(["-a", "./"])
    ls.prepare()

    print(ls.runner.args)

    ls.run()
    assert(ls.state == State.SUCCEEDED)

    local["rmdir"](ls.path)     # cleanup
