#!/usr/bin/env python3
"""Russian-labelled figures for the report (report/build_report.js): statics and dynamics charts, image copies."""
import csv
import os
import shutil

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "report", "img")
os.makedirs(IMG, exist_ok=True)
INK, MUTE, BLUE, ORANGE, GRID = "#1b2026", "#5d6670", "#2a5d9f", "#d9631f", "#d5d9de"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

# ---- statics: worst-pose gravity torque, % of the reducer rated torque (robot/RTC-7-statics.md)
J = ["J2 ШМ-1000", "J3 ШМ-500", "J4 ШМ-500", "J5 ШМ-150", "J6 ШМ-150"]
own = np.array([869, 249, 217, 29, 13], float)
pay = np.array([1075 - 869, 365 - 249, 326 - 217, 54 - 29, 33 - 13], float)
rated = np.array([1000, 375, 375, 103, 103], float)
ss = np.array([1960, 675, 675, 155, 155], float)
fig, ax = plt.subplots(figsize=(8.5, 3.6))
y = np.arange(len(J))[::-1]
ax.barh(y, 100 * own / rated, color=BLUE, height=0.55, label="собственный вес")
ax.barh(y, 100 * pay / rated, left=100 * own / rated, color=ORANGE, height=0.55, label="груз 8 кг")
for yi, o, p, r in zip(y, own, pay, rated):
    ax.text(160, yi, f"{o + p:.0f} / {r:.0f} Н·м ({100 * (o + p) / r:.0f} %)", va="center", ha="right", fontsize=9, color=INK)
ax.axvline(100, color=INK, lw=1.2)
ax.text(101, y[0] + 0.45, "номинал", fontsize=8, color=INK)
ax.set_yticks(y, J)
ax.set_xlim(0, 160)
ax.set_xticks([0, 20, 40, 60, 80, 100])
ax.set_xlabel("статический момент в худшей позе, % номинального момента редуктора")
ax.grid(axis="x", color=GRID)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2, frameon=False)
fig.tight_layout()
fig.savefig(os.path.join(IMG, "statics.png"), dpi=200)
plt.close(fig)

# ---- dynamics: torque along the demo program, % of the start-stop torque (sim/RTC-7/RTC-7-demo-torques-ref.csv)
with open(os.path.join(ROOT, "sim", "RTC-7", "RTC-7-demo-torques-ref.csv"), encoding="utf-8") as f:
    r = list(csv.reader(f))
D = np.array([[float(v) for v in row] for row in r[1:]])
t, tau, grav = D[:, 0], D[:, 1:8], D[:, 8:15]
drive = ["ШМ-150м", "ШМ-1000", "ШМ-500", "ШМ-500", "ШМ-150", "ШМ-150", "ШМ-60"]
tss = np.array([155, 1960, 675, 675, 155, 155, 93], float)
trat = np.array([103, 1000, 375, 375, 103, 103, 62], float)
fig, axs = plt.subplots(7, 1, figsize=(8.5, 10.5), sharex=True)
for k, ax in enumerate(axs):
    ax.plot(t, 100 * grav[:, k] / tss[k], color="#a9b1ba", lw=1.3, label="от веса")
    ax.plot(t, 100 * tau[:, k] / tss[k], color=BLUE, lw=1.6, label="с ускорениями")
    for v, ls in ((100, "--"), (-100, "--"), (100 * trat[k] / tss[k], ":"), (-100 * trat[k] / tss[k], ":")):
        ax.axhline(v, color=MUTE, lw=0.8, ls=ls)
    lim = max(110, 110 * np.abs(tau[:, k]).max() / tss[k])
    ax.set_ylim(-lim, lim)
    ax.set_ylabel(f"J{k + 1}\n{drive[k]}", rotation=0, ha="right", va="center", fontsize=9)
    pk = np.abs(tau[:, k]).max()
    ax.text(1.0, 0.9, f"пик {pk:.0f} Н·м = {100 * pk / tss[k]:.0f} % пускового {tss[k]:.0f}", transform=ax.transAxes,
            ha="right", va="top", fontsize=8.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
axs[0].legend(loc="upper left", frameon=False, ncol=2, fontsize=8.5)
axs[-1].set_xlabel("время программы, с")
fig.text(0.01, 0.995, "% пускового момента редуктора; пунктир — ±100 %, точки — номинальный момент", fontsize=9,
         va="top", color=MUTE)
fig.tight_layout(rect=(0, 0, 1, 0.985))
fig.savefig(os.path.join(IMG, "dynamics.png"), dpi=200)
plt.close(fig)

# ---- image copies
COPY = {
    "arm.png": "robot/anim/stills/h_cover.png",
    "zero.png": "robot/anim/stills/h_zero.png",
    "user_scheme.png": "robot/RTC-7-user-scheme.png",
    "shoulder.png": "robot/anim/stills/c1_shoulder.png",
    "elbow.png": "robot/anim/stills/c2_elbow.png",
    "wrist.png": "robot/anim/stills/c3_wrist.png",
    "j3turn.png": "robot/anim/stills/h_j3.png",
    "reach.png": "robot/anim/stills/h_reach.png",
    "zones.png": "robot/RTC-7-payload-zones-ru.png",
    "fea_if_link3.png": "fea/RTC-7/pictures/LINK-3.png",
    "fea_link3_C.png": "fea/RTC-7/ccx/plots/LINK-3_C.png",
    "fea_link1_C.png": "fea/RTC-7/ccx/plots/LINK-1_C.png",
    "fea_link3_D.png": "fea/RTC-7/ccx/plots/LINK-3_D.png",
}
for dst, src in COPY.items():
    shutil.copy(os.path.join(ROOT, src), os.path.join(IMG, dst))
print("figures ->", IMG)
