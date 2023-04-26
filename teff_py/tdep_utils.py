import numpy as np

from plumbum import local
from plumbum.cmd import grep, awk, head, tail


def get_overdetermination_report(fname):
    """Obtain data on the grade of FCs equations system overdetermination
    from the `extract_forceconstants` output file `fname`.

    Result: {fc_order: (num_fcs_upto_this_order, overdetermination_grade), ...}
    """
    results = {}
    for fc in [2, 3, 4]:
        pipe = grep["-A4", "REPORT GRADE OF OVERDETERMINATION", fname] | \
            grep[f"up {fc}. order"] | \
            awk['{ print $7, $11 }']
        res = pipe(retcode=None).strip()
        if len(res) > 0:
            num, ratio = res.split()
            results[fc] = (int(num), float(ratio))

    return results


def get_r_squared(fname):
    """Obtain `R-squared` coefficient of determination for the fit
    from `extract_forceconstants` output file `fname`.

    Result: {fc_order: r_squared, ...}"""
    results = {}
    for fc, label in [(2, "second"),
                      (3, "third"),
                      (4, "fourth")]:
        pipe = grep["-A4", "R^2", fname] | \
            grep[f"{label} order"] | \
            awk['{ print $3 }']
        res = pipe(retcode=None).strip()
        if len(res) > 0:
            r_squared = float(res)
            results[fc] = r_squared

    return results


def get_interactions(fname):
    """Read number of shells and forceconstants
    from `extract_forceconstants` output file `fname`.

    Result: {fc_order: (num_shells, num_fcs), ...}
    """
    results = {}
    for fc, label in [(1, "first"),
                      (2, "second"),
                      (3, "third"),
                      (4, "fourth")]:
        pipe = grep["-A4", "Interactions:", fname] | \
            grep[f"{label}order forceconstant:"] | \
            awk['{ print $3, $4 }']
        res = pipe(retcode=None).strip().split()
        results[fc] = (res[0], res[1])

    return results


def get_elastic_constants(fname):
    """Read elastic constants matrix in a `numpy` format
    from `extract_forceconstants` output file `fname`.
    """
    pipe = grep["-A6", "elastic constants", fname] | tail[-6]
    data = ";".join(pipe().strip().split("\n"))

    return np.matrix(data, dtype=float)


def get_rcmax(fname):
    "`fname` is usually `infile.ssposcar`" 

    alat = float((head[-2, fname] | tail[-1])().strip())

    cell = (head[-5, fname] | tail[-3])().strip()
    cell = np.matrix(";".join(cell.split("\n"))) * alat
    rcmax = np.min(np.sqrt(np.sum(np.square(cell), axis=(1))).flatten()) * 0.5
        
    return rcmax