#!/usr/bin/python
#^FIXME: edit path to the python executable

# system-related imports:
import logging
import os.path as op
import pprint
# imports from `plumbum` for shell commands
# and cli-application wrapper:
from plumbum import local, cli
from plumbum.cmd import cp, ln, mkdir, cat, pwd, head, tail, awk, echo, grep

# my workflow engine actions:
from teff_py.actions import ActionLocal, State

# Materials Project API
from mp_api.client import MPRester

MP_API_KEY = ""  #FIXME: Materials Project key 
mpr = MPRester(MP_API_KEY)
PSEUDOS_DIR = "/path/to/pseudos" #FIXME: path to pseudopotential files collection

pp = pprint.PrettyPrinter(indent=4)
# import numpy as np
# import pandas as pd
# import seaborn as sns
# import matplotlib.pyplot as plt

# Logging Setup.
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%d-%m-%Y %H:%M',
    filename='wf.log',
    filemode='w',
)
console = logging.StreamHandler()
# console.setLevel(logging.INFO)
console.setLevel(logging.WARNING)
console.setFormatter(
    logging.Formatter(
        '%(asctime)s %(name)-12s %(message)s',
        datefmt='%d-%m-%Y %H:%M',))
logging.getLogger('').addHandler(console)


# Definitions for Workflow Actions.
class GenStruct(ActionLocal):
    "Supercell generation stage from incoming structure."
    command = local["generate_structure"]
    num_mpi_procs = 2

    def make_args_list(self):
        structure = self.args_source["structure"]
        return ["-na", len(structure)*16] # hard-coded SC size

    @ActionLocal.change_state_on_prepare  # this decorator is required
    def prepare(self):
        # link ucposcar that was downloaded from MP
        ln(self.path+"/../infile.ucposcar",
           self.path+"/infile.ucposcar")


class CanConf(ActionLocal):
    "Canonical configuration stage inside of the main convergence iteration."
    command = local["canonical_configuration"]
    num_mpi_procs = None  # force non-MPI job

    def make_prefix(self):
        # the label will look like: `{classname}.{iiter}`
        return "".join([
            self.__class__.__name__.lower(),
            ".", str(self.args_source["iiter"]),
        ])

    def make_args_list(self):
        return ["-n",  self.args_source["nconfs"],
                "-td", self.args_source["td"],
                "-of", 5]       # generate configuration for SIESTA

    @ActionLocal.change_state_on_prepare
    def prepare(self):
        ln(self.parent.path+"/infile.ucposcar",
           self.path+"/infile.ucposcar")
        ln(self.parent.path+"/outfile.ssposcar",
           self.path+"/infile.ssposcar")


class SpSiesta(ActionLocal):
    "Single-point configuration processing with SIESTA."
    command = ["siesta"]
    num_mpi_procs = 16

    def make_prefix(self):
        return "".join([
            self.__class__.__name__.lower(),
            ".", str(self.args_source["nc"]),
        ])

    def make_args_list(self):
        return [self.path+"/siesta_conf"+("%04d" % self.args_source["nc"])]

    @ActionLocal.change_state_on_prepare
    def prepare(self):
        list(map(lambda fname: ln(self.parent.path+fname, self.path+fname),
                 ["/siesta_conf"+("%04d" % self.args_source["nc"]),
                  "/siesta_conf"+("%04d" % self.args_source["nc"])+".XV"]))

        for specie in self.args_source["structure"].species:
            if not local.path(self.path+"/"+specie.name+".psf").exists():
                ln(PSEUDOS_DIR+"/"+specie.name+".psf",
                   self.path+"/"+specie.name+".psf")


class FCs(ActionLocal):
    "Extract forceconstants from SIESTA calculations with TDEP."
    command = ["extract_forceconstants"]
    num_mpi_procs = 2

    def make_args_list(self):
        # we expect to receive a source collection like:
        # {"rc2": 6.0, "rc3": 5.0}
        # from it we build a list of switches and args to our shell command:
        return [ "-rc2", 5.0, "-rc3", 4.0 ]

    @ActionLocal.change_state_on_prepare
    def prepare(self):
        list(map(lambda fname: ln(self.parent.path+"/"+fname, self.path+"/"+fname),
                 ["infile.ssposcar", "infile.ucposcar"]))

        for nc in range(1, self.args_source["nconfs"]+1):
            pipe = cat[self.parent.path+"/spsiesta."+str(nc)+"/siesta_conf"+("%04d" % nc)+".STRUCT_OUT"] | \
                tail[-self.args_source["na_supercell"]] | awk['{ print $3, $4, $5 }']
            cmd = pipe >> self.path + "/infile.positions"
            cmd()

        for nc in range(1, self.args_source["nconfs"]+1):
            pipe = cat[self.parent.path+"/spsiesta."+str(nc)+"/siesta_conf"+("%04d" % nc)+".FA"] | \
                tail[-self.args_source["na_supercell"]] | awk['{ print $2, $3, $4 }']
            cmd = pipe >> self.path + "/infile.forces"
            cmd()

        # infile.meta
        (echo[self.args_source["na_supercell"]] >> self.path+"/infile.meta")()
        (echo[self.args_source["nconfs"]] >> self.path+"/infile.meta")()
        (echo[1.0] >> self.path+"/infile.meta")()  # timestep?
        (echo[300] >> self.path+"/infile.meta")()  # temperature?

        # infile.stat
        for nc in range(1, self.args_source["nconfs"]+1):
            i = nc
            t = float(nc-1)

            pipe = grep["Etot ", self.parent.path+"/spsiesta."+str(nc)+"/out.log"] | tail[-1] | awk['{ print $4 }']
            Etot = float(pipe().strip())

            pipe = grep["Ekin ", self.parent.path+"/spsiesta."+str(nc)+"/out.log"] | tail[-1] | awk['{ print $4 }']
            Ekin = float(pipe().strip())
            
            Epot = Etot - Ekin
            
            # tail -2 out.log | head -1 | tail -1 | awk '{ print $4 }'
            pipe = tail[-self.args_source["nconfs"], self.parent.path+"/out.log"] | \
                head[-nc] | tail[-1] | awk['{ print $4 }']
            T = float(pipe().strip())  # temperature?
            pipe = grep["-i", "-A4", "pres", self.parent.path+"/spsiesta."+str(nc)+"/out.log"] | tail[-1] | awk['{ print $2 }']
            P = float(pipe().strip()) * 0.1
            
            pipe = grep["-i", "-A3", "Stress ", self.parent.path+"/spsiesta."+str(nc)+"/out.log"] | tail[-3] | awk['{ print $2, $3, $4 }']
            stres_line = " ".join(pipe().strip().split("\n"))

            line = f"{i} {nc} {Etot} {Epot} {Ekin} {T} {P} {stres_line}"
            (echo[line] >> self.path+"/infile.stat")()  
            

class TC(ActionLocal):
    command = local["thermal_conductivity"]  # this executable should be visible in $PATH
    num_mpi_procs = 16

    def make_args_list(self):
        # qg = self.args_source["qg"]
        return [
            "-qg", 20, 20, 20,
            "--temperature", str(300)
        ]

    @ActionLocal.change_state_on_prepare  # this decorator is required
    def prepare(self):
        # link ucposcar from the parent calculation
        ln(self.parent.path+"/infile.ucposcar", 
           self.path+"/infile.ucposcar")
        # link AND rename forceconstant files
        files = ["forceconstant", "forceconstant_thirdorder"]
        for fname in files:
            ln(self.parent.path+"/outfile."+fname,
               self.path+"/infile."+fname)


class WfApp(cli.Application):
#     qg_max = cli.SwitchAttr("--qg-max", int, default=5, help="max num of q-points along each coordinate")

    def main(self, m_id):

        # 1. Retrieval of structure from Materials Project:
        # if not local.path(pwd().strip()+"/infile.ucposcar").exists():

        structure = mpr.get_structure_by_material_id(m_id, final=False)[0]
        # ^returns 'list' of initial structures
        # structure = mpr.get_structure_by_material_id(m_id)  # that will fail the symmetry. Relax?
        print(structure)
        structure.to(fmt='poscar', filename="infile.ucposcar")
        # structure.formula.lower()
        # structure.species[0].name
        # assert(structure.is_3d_periodic)

        # 2. Supercell generation with TDEP:
        gen_struct = GenStruct({"structure": structure})
        gen_struct.prepare()
        gen_struct.run()

        # Line 7 of the outfile.ssposcar contains resulting number of atoms:
        pipe = head["-7", gen_struct.path+"/outfile.ssposcar"] | tail["-1"]
        # na_supercell = int(pipe().strip())
        na_supercell = sum(list(map(int, pipe().strip().split())))

        # 3. Iteration over canonical configurations.
        results = {}
        for iiter in range(0, 6):

            td = 300
            nconfs = 2**(iiter + 1) // 2
            can_conf = CanConf({"nconfs": nconfs, "td": td, "iiter": iiter},
                               parent=gen_struct)
            can_conf.prepare()
            can_conf.run()

            # sp_calcs = []

            for nc in range(1, nconfs+1):
                sp_siesta = SpSiesta({"nc": nc, "structure": structure},
                                     parent=can_conf)
                sp_siesta.prepare()
                sp_siesta.run()  

            fcs = FCs({"nconfs": nconfs, "na_supercell": na_supercell}, parent=can_conf)
            fcs.prepare()
            fcs.run()
        
            tc = TC([], parent=fcs)
            tc.prepare()
            tc.run()

            tc_line = cat(op.join(tc.path, "outfile.thermal_conductivity"))
            tc_res = float(tc_line.strip().split()[1])
            results[iiter] = tc_res
            print(iiter, tc_res)
            
        # pp.pprint(results)

if __name__ == "__main__":
    WfApp.run()
