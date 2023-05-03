import math
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv("results.csv")

# sns.heatmap(
#     df.pivot(index='stride', columns='rc2', values='r_squared'),
#     cmap="Spectral",
#     vmin=0.0,
#     vmax=1.0,
#     annot=True,
# ).set(title="Value of R^2 as it varies with `stride` and `rc2` in KCl")

# df.overd = df.overd.map(lambda x: math.floor(math.log(x, 10)))
# sns.heatmap(
#     df.pivot(index='stride', columns='rc2', values='overd'),
#     # cmap="mako",
#     cmap="rocket",
#     vmin=0,
#     vmax=5,
#     # annot=True,
# ).set(title="Value of overdetermination level as it varies with `stride` and `rc2` in KCl")

sns.heatmap(
    df.pivot(index='stride', columns='rc2', values='dfreq_rel_max_gamma'),
    # df.pivot(index='stride', columns='rc2', values='dfreq_rel_max_edge'),
    cmap="Spectral",
    annot=True,
).set(title="Value of optical phonon frequency at Gamma as it varies with `stride` and `rc2` in KCl")

plt.show()
