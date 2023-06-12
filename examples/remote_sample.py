import logging
from plumbum.machines.paramiko_machine import ParamikoMachine
from plumbum.path.utils import copy

from teff_py.actions import Action, State
from teff_py.tdep_utils import get_rcmax

# logging.basicConfig(
#     level=logging.DEBUG,
#     format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
#     datefmt='%d-%m-%Y %H:%M',
#     # filename='wf.log',
#     # filemode='w',
# )

# ## Utility functions definitions
def read_temperature(fname):
    "Return temperature from `fname` that shoud be `infile.meta`"
    return float(local["tail"]("-1", fname).strip())

# ## Setup Machines
# Local Machine
from plumbum import local

# Remote Machine
#TODO: These should be set as an input/config file.
rem = ParamikoMachine()

# chdir to working directory
local.cwd.chdir("~/Projects/workflows/10-remote-test")
# local["pwd"]()

# local input repository
#TODO: Scatter over those.
inp_repo_dir = local.path("~/Projects/workflows/digest")
with local.cwd(inp_repo_dir):
    inp_systems = local["ls"]().split()

inp_sys = inp_systems[len(inp_systems)-1]
inp_path = inp_repo_dir / inp_sys
# inp_path = local.path() / inp_sys

loc_base_path = local.path("~/Projects/workflows/10-remote-test")
loc_path = loc_base_path / inp_sys

rem_base_path = rem.path("~/Projects/workflows/10-remote-test")
rem_path = rem_base_path / inp_sys

#NOTE copy(inp_path, loc_path)        # works
copy(inp_path, rem_path)        # works

# env enhancer for remote HPC command invocations to actually work
renv = rem["env"]["LD_LIBRARY_PATH=%s" % rem.env.get("LD_LIBRARY_PATH")]
rmpi = renv[rem["mpirun"]["-np", 8]]

# ## workflow Action stage specifications
class ForceConstants(Action):
    command = rmpi[rem["extract_forceconstants"]]
    # command = renv[rem["extract_forceconstants"]]
    # command = renv[rem["extract_forceconstants"]]
    # num_mpi_procs = None  # TODO: deprecate it, add decorator

    def make_args_list(self):
        return ["-rc2",
                ("%.3f" % self.args_source["rc2"]),
                # self.args_source["rc2"],
                # "-U0",
                ]

    def make_prefix(self):
        return "".join([
            "work", "/",
            "fcs", "_",
            ("%.3f" % self.args_source["rc2"]),
            # "_",
            # ("%04d" % self.args_source["stride"]),
        ])

    @Action.change_state_on_prepare
    def prepare(self):
        files = ["forces", "meta", "positions", "ssposcar", "stat", "ucposcar"]
        for fname in files:
            rem["ln"]("-s",
                      self.path+"/../../infile."+fname,
                      self.path+"/infile."+fname)

# ##

local.cwd.chdir(loc_path)
rem.cwd.chdir(rem_path)

fc_calc = ForceConstants({"rc2": get_rcmax("infile.ssposcar")})
fc_calc.prepare()
fc_calc.run()
