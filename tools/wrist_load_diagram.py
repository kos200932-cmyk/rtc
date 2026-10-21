#!/usr/bin/env python3
"""J7 load diagram: how far from the flange the centre of mass of the payload may be (tilting moment and torque
of the J7 reducer).    python tools/wrist_load_diagram.py [--red KB14] [--use 0.9] [--kd 1.05] [--kstop 1.3]

Rules (worst orientation of J7 - its axis horizontal, the gravity at right angles to the offset):
  tilting:  kd * g * (m * R + M0/g) <= use * M_tilt        R = distance flange centre -> payload COM, mm
            kstop * g * (m * R + M0/g) <= M_tilt            emergency stop (deceleration kstop - 1 in g)
  torque:   kd * g * m * e <= use * T_rated                e = COM off the J7 axis
M0 = moment of the interface (4 kg, COM 30 mm beyond the flange) + J7 output shaft, from tools/layout_select.py.
kd 1.05: 0.2 rad/s / 0.1 rad/s^2 of all joints give <= ~0.04 g at the flange.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_select as ls  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = 9.81
INK, MUTE, BLUE, ORANGE, RED, GRID = "#1b2026", "#5d6670", "#2a5d9f", "#d9631f", "#c62828", "#d5d9de"


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    ap = argparse.ArgumentParser()
    ap.add_argument("--red", default="KB14")
    ap.add_argument("--alt", default="KB17")
    ap.add_argument("--use", type=float, default=0.9)
    ap.add_argument("--kd", type=float, default=1.05)
    ap.add_argument("--kstop", type=float, default=1.3)
    ap.add_argument("--m0", type=float, default=4.0 * 0.030 + 0.311 * 0.041, help="kg*m: interface + output shaft")
    ap.add_argument("--png", default=os.path.join(ROOT, "robot", "RTC-7-J7-load-diagram.png"))
    a = ap.parse_args()
    cat = ls.read_catalog(os.path.join(ROOT, "components", "DMRD", "KB-series.txt"))

    def rmax(r, m):
        work = (a.use * r["Mt"] / a.kd / G - a.m0) / m
        stop = (r["Mt"] / a.kstop / G - a.m0) / m
        return np.minimum(work, stop) * 1e3, work * 1e3, stop * 1e3

    def emax(r, m):
        return a.use * r["T"] / a.kd / G / m * 1e3

    R, A = cat[a.red], cat[a.alt]
    m = np.linspace(1, 12, 200)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.2), gridspec_kw={"width_ratios": [1.15, 1]})
    for r, col, ls_ in ((R, BLUE, "-"), (A, MUTE, "--")):
        lim, w, s = rmax(r, m)
        ax1.plot(m, lim, color=col, lw=2.4 if r is R else 1.6, ls=ls_,
                 label=f"{r['name']}: R доп. (M_tilt {r['Mt']:g} Н·м)")
        if r is R:
            ax1.plot(m, w, color=col, lw=0.9, ls=":", label=f"{r['name']}: только рабочий режим")
            ax1.fill_between(m, 0, lim, color=col, alpha=0.08)
    for mk in (2, 4, 6, 8, 10):
        v = rmax(R, mk)[0]
        ax1.plot(mk, v, "o", color=BLUE, ms=5)
        ax1.annotate(f"{v:.0f}", (mk, v), textcoords="offset points", xytext=(4, 6), fontsize=9, color=INK)
    ax1.axvline(8, color=ORANGE, lw=1)
    ax1.text(8.1, ax1.get_ylim()[1] * 0.02 if False else 20, "8 кг", color=ORANGE, fontsize=9)
    ax1.set_ylim(0, 700)
    ax1.set_xlim(1, 12)
    ax1.set_xlabel("масса груза (захват + деталь), кг")
    ax1.set_ylabel("R — расстояние от центра фланца J7 до центра масс груза, мм")
    ax1.set_title(f"Допустимое удаление центра масс груза, J7 {a.red}", fontsize=11, color=INK, loc="left")
    ax1.grid(color=GRID)
    ax1.legend(frameon=False, fontsize=8.8)
    # L - e plane for 8 kg
    mm = 8.0
    for r, col, ls_ in ((R, BLUE, "-"), (A, MUTE, "--")):
        rr = rmax(r, mm)[0]
        ee = emax(r, mm)
        t = np.linspace(0, np.pi / 2, 200)
        x, y = rr * np.cos(t), rr * np.sin(t)
        y = np.minimum(y, ee)
        ax2.plot(x, y, color=col, lw=2.4 if r is R else 1.6, ls=ls_,
                 label=f"{r['name']}: R ≤ {rr:.0f} мм, e ≤ {min(ee, rr):.0f} мм")
        if r is R:
            ax2.fill_between(x, 0, y, color=col, alpha=0.1)
    ax2.plot(100, 0, "s", color=ORANGE, ms=8)
    ax2.annotate("расчётный груз\n(L 100, e 0)", (100, 0), textcoords="offset points", xytext=(6, 10), fontsize=8.5,
                 color=ORANGE)
    ax2.set_xlim(0, 560)
    ax2.set_ylim(0, 400)
    ax2.set_aspect("equal")
    ax2.set_xlabel("L — вылет центра масс вдоль оси J7 от фланца, мм")
    ax2.set_ylabel("e — смещение центра масс от оси J7, мм")
    ax2.set_title("Зона центра масс груза 8 кг", fontsize=11, color=INK, loc="left")
    ax2.grid(color=GRID)
    ax2.legend(frameon=False, fontsize=8.8, loc="upper right")
    fig.suptitle(f"RTC-7, J7: ограничение груза по опрокидывающему и крутящему моменту редуктора\n"
                 f"интерфейс 4 кг учтён; рабочий режим ≤ {a.use * 100:.0f} % при kд {a.kd:g}, "
                 f"аварийный останов ≤ 100 % при kст {a.kstop:g}".replace(".", ","),
                 fontsize=11.5, x=0.01, ha="left", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(a.png, dpi=150, facecolor="white")
    print("->", a.png)
    for r in (R, A):
        for mk in (2, 4, 6, 8, 10, 12):
            lim, w, s = rmax(r, mk)
            print(r["name"], mk, "kg: R <=", round(float(lim)), "(work", round(float(w)), "stop", round(float(s)), ") e <=",
                  round(emax(r, mk)))


if __name__ == "__main__":
    main()
