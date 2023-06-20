class CommandComposer(object):
    @staticmethod
    def __compose_commands(*fs):
        def composition(x, **kws):
            for f in fs[::-1]:
                x = f(x, **kws)
            return x
        return composition

    def __init__(self, *commands):
        self._composition = self.__compose_commands(*commands)
        
    def __call__(self, command, **kws):
        return self._composition(command, **kws)


def wrap_mpirun(command, **kws):
    if "num_mpi_procs" in kws:
        mpirun = command.machine["mpirun"]["-np", kws["num_mpi_procs"]]
    else:
        mpirun = command.machine["mpirun"]

    return mpirun[command]


def wrap_mprof(command, **kws):
    if "mprof_include_children" in kws and kws["mprof_include_children"]:
        mprof = command.machine["mprof"]["run", "--include-children"]
    elif "mprof_multiprocess" in kws and kws["mprof_multiprocess"]:
        mprof = command.machine["mprof"]["run", "--multipocess"]
    else:
        mprof = command.machine["mprof"]["run"]

    return mprof[command]


def wrap_ld_library_path(command, **kws):
    machine = command.machine
    ld_lib_env = machine["env"]["LD_LIBRARY_PATH=%s" %
                                machine.env.get("LD_LIBRARY_PATH")]

    return ld_lib_env[command]


hpc_wrapper = CommandComposer(
    wrap_ld_library_path,
    wrap_mprof,
    wrap_mpirun)
