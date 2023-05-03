#!/usr/bin/python

import logging
import os.path as op
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from plumbum import local, cli
from plumbum.cmd import cp, ln, pwd, mkdir, awk, head, tail

from teff_py.actions import ActionLocal, State
from teff_py.tdep_utils import get_rcmax, get_overdetermination_report, get_r_squared

### Utility functions definitions
def read_temperature(fname):
    "Return temperature from `fname` that shoud be `infile.meta`"
    return float(tail("-1",fname).strip())
    
def read_phonons_gamma(fname):
    """Read an array of frequency values of the optical branches at Gamma.
    Asserts that the values come really from the Gamma point."""
    nums = np.array(list(map(float, head("-n1",fname).strip().split())))
    #assert we are really at gamma:
    assert(nums[0]==0.0)
    #return the non-zero values:
    return nums[nums != 0]

def read_phonons_edge(fname):
    """Read an array of frequency values of the phonon branches
    _presumably_ at the edge of a Brillouin zone (bottom of the output file). 
    That _presumably_ needs to be checked."""
    nums = list(map(float, tail("-1",fname).strip().split()))
    #return the values from optical branches:
    return nums[1:]

### Workflow stage specifications
class ForceConstants(ActionLocal):
    command = local["extract_forceconstants"]
    num_mpi_procs = 16

    def make_args_list(self):
        return ["-rc2", self.args_source["rc2"],
                "--stride", self.args_source["stride"]]

    def make_prefix(self):
        return "".join([
            "work", "/",
            "forceconstants", "_",
            ("%.3f" % self.args_source["rc2"]), "_",
            ("%04d" % self.args_source["stride"]),
        ])

    @ActionLocal.change_state_on_prepare
    def prepare(self):
        files = ["forces", "meta", "positions", "ssposcar", "stat", "ucposcar"]
        for fname in files:
            ln(self.path+"/../../infile."+fname,
               self.path+"/infile."+fname)


class PhDispRel(ActionLocal):
    command = local["phonon_dispersion_relations"]
    num_mpi_procs = 16

    def make_args_list(self):
        return ["--temperature", self.args_source["temperature"]]

    def make_prefix(self):
        return self.__class__.__name__.lower()

    @ActionLocal.change_state_on_prepare
    def prepare(self):
        ln(self.parent.path+"/infile.ucposcar",
           self.path+"/infile.ucposcar")
        ln(self.parent.path+"/outfile.forceconstant",
           self.path+"/infile.forceconstant")

### Workflow App definition
class WfApp(cli.Application):
    rc2_step = cli.SwitchAttr("--rc2_step", float, default=0.25, help="step of `rc2` cutoff value")
    max_stride = cli.SwitchAttr("--max_stride", int, default=100, help="maximum `stride` skipping value")
    stride_step = cli.SwitchAttr("--stride_step", int, default=10, help="step of `stride` skipping value") 

    console = logging.StreamHandler()
    verbose_output = cli.Flag("-v", default=False)

    def logging_setup(self):
        "Setup logging handlers for the application"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            datefmt='%d-%m-%Y %H:%M',
            filename='wf.log',
            filemode='w',)

        # define a Handler which writes INFO messages or higher to the
        # sys.stderr
        if self.verbose_output:
            self.console.setLevel(logging.INFO)
        else:
            self.console.setLevel(logging.WARNING)

        self.console.setFormatter(
            logging.Formatter(
                '%(asctime)s %(name)-12s %(message)s',
                datefmt='%d-%m-%Y %H:%M',))

        # add the handler to the root logger
        logging.getLogger('').addHandler(self.console)

    ### Main workflow procedure
    def main(self):

        self.logging_setup()

        rcmax = get_rcmax("infile.ssposcar")
        temperature = read_temperature("infile.meta")

        stride_range = list(range(1, self.max_stride+1, self.stride_step))
        rc_range = list(np.arange(2.0, rcmax, self.rc2_step))
        
        # perform the most top-right calculation:
        fc_calc = ForceConstants({"rc2": rc_range[-1], "stride": 1}) # max_rc2 & stride=1 calculations
        fc_calc.prepare()
        fc_calc.run()

        ph_disp = PhDispRel({"temperature": temperature}, parent=fc_calc) 
        ph_disp.prepare()
        ph_disp.run()
        
        # read what we consider to be `the most correct` reference phonon dispersion 
        reference_phonons_at_gamma = \
            read_phonons_gamma(ph_disp.path+"/outfile.dispersion_relations")
        reference_phonons_at_gamma = np.array(reference_phonons_at_gamma) # coerce to np.array

        reference_phonons_at_edge = \
            read_phonons_edge(ph_disp.path+"/outfile.dispersion_relations")
        reference_phonons_at_edge = np.array(reference_phonons_at_edge) # coerce to np.array

        # define results dataframe header
        df = pd.DataFrame([], columns=[
            "stride",
            "rc2", 
            "r_squared", 
            "num_fcs", 
            "overd", 
            "dfreq_rel_max_gamma",
            "dfreq_rel_max_edge",
            ])

        for stride in stride_range:
            for rc2 in rc_range:
                fc_calc = ForceConstants({"rc2": rc2, "stride": stride})
                fc_calc.prepare()
                fc_calc.run()
                
                ph_disp = PhDispRel({"temperature": temperature}, parent=fc_calc) 
                ph_disp.prepare()
                ph_disp.run()
                phonons_at_gamma = np.array(  # coerce to np.array
                    read_phonons_gamma(ph_disp.path+"/outfile.dispersion_relations"))
                dfreq_rel_max_gamma = \
                    np.nanmax(abs(reference_phonons_at_gamma - phonons_at_gamma) / reference_phonons_at_gamma)

                phonons_at_edge = np.array(  # coerce to np.array
                    read_phonons_edge(ph_disp.path+"/outfile.dispersion_relations"))
                dfreq_rel_max_edge = \
                    np.nanmax(abs(reference_phonons_at_edge - phonons_at_edge) / reference_phonons_at_edge)
                
                df.loc[len(df)] = [
                    stride,
                    rc2, 
                    get_r_squared(fc_calc.path+"/out.log")[2],
                    get_overdetermination_report(fc_calc.path+"/out.log")[2][0],
                    get_overdetermination_report(fc_calc.path+"/out.log")[2][1],
                    dfreq_rel_max_gamma,
                    dfreq_rel_max_edge,
                ]

        print(df)
        df.to_csv('results.csv')

if __name__ == "__main__":
    WfApp.run()
