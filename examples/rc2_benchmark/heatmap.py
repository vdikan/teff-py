import math
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from plumbum.cmd import pwd, head, tail

# obtain labels from the .csv file header:
header = head("-1", "results.csv").strip().split(",")
syslabel = header[0]
edge_kpoint_label = header[-1].split("_")[-1]

# obtain extra metadata
num_atoms = head("-1", "infile.meta").strip()
num_confs = (head["-2", "infile.meta"] | tail["-1"])().strip()

# load data
df = pd.read_csv("results.csv")

# setup canvas
plt.rcParams.update({'font.size': 6})
# fig, axes = plt.subplots(2, 2, sharex=True)
# fig, axes = plt.subplots(2, 2)
fig, axes = plt.subplots(2, 2, figsize=(20,10))
plt.rcParams.update({'font.size': 10})
fig.suptitle("""Determination coefficients and maximum phonon frequency relative errors obtained from TDEP 
w/r to the `rc2` cutoff and `stride` parameter in """ + r"$\bf{" + syslabel +"}$  "+
f"[ {num_atoms} atoms; {num_confs} configurations ]")

plt.rcParams.update({'font.size': 8})

# plot the panels
sns.heatmap(
    df.pivot(index='stride', columns='rc2', values='r_squared'),
    ax=axes[0,0],
    cmap="Spectral",
    vmin=0.0,
    vmax=1.0,
    annot=True,
    annot_kws={"size":6},
    fmt=".2f",
).set(title=f"R^2 as it varies with `stride` and `rc2` in {syslabel}")

df.overd = df.overd.map(lambda x: math.floor(math.log(x, 10)))
sns.heatmap(
    df.pivot(index='stride', columns='rc2', values='overd'),
    ax=axes[1,0],
    cmap="rocket",
    vmin=0,
    vmax=5,
).set(title=f"log(overdetermination_level) of the fit for {syslabel}, rounded down")

sns.heatmap(
    df.pivot(index='stride', columns='rc2', values=header[-2]),
    ax=axes[0,1],
    cmap="YlOrBr",
    annot=True,
    annot_kws={"size":6},
    fmt=".2f",
).set(title=f"max phonon dispersion relative error at Gamma point in {syslabel}")

sns.heatmap(
    df.pivot(index='stride', columns='rc2', values=header[-1]),
    ax=axes[1,1],
    cmap="YlOrBr",
    annot=True,
    annot_kws={"size":6},
    fmt=".2f",
).set(title=f"max phonon dispersion relative error at {edge_kpoint_label} point in {syslabel}")

# save and display
plt.savefig('chart.pdf', dpi=300)  
plt.show()