#!/usr/bin/env python3
"""Joint torques with accelerations along the demo program (inverse dynamics on the URDF, Pinocchio).

    python tools/robot_dynamics.py [--urdf sim/RTC-7/RTC-7.urdf] [--traj sim/RTC-7/RTC-7-demo-traj.csv]
                                   [--speed 1.0] [--md robot/RTC-7-dynamics.md] [--png robot/RTC-7-dynamics.png]

The joint angles (30 fps) are interpolated by a cubic spline -> q, dq, ddq; RNEA gives the torque about
every axis = gravity + inertia + Coriolis of the links (the URDF masses: designed links, catalog joint
masses, interface 4 kg, payload as exported). --speed k runs the same path k times faster (the inertial
part grows as k^2). NOT included (ASSUMED zero): reflected rotor inertia of the motors, friction /
efficiency of the reducers, cable forces. The same model in Simscape: sim/RTC-7/rtc7_build.m.
"""
import argparse
import csv
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        r = list(csv.reader(f))
    return r[0], np.array([[float(v) for v in row] for row in r[1:]])


def card_torques(names):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import joint_envelope as je
    import robot_scheme as rs
    import robot_statics as st
    lay = rs.read_layout(os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    out = []
    for a in lay["axes"]:
        jn = a["joint"].rstrip("m")
        j = je.read_joint(os.path.join(ROOT, "joints", jn, jn + ".txt"))
        rd = st.card_data(os.path.join(ROOT, j["use"]["reducer"]))
        out.append((a["joint"], float(rd.get("T_design", rd["T_rated"])), float(rd["T_startstop"])))
    return out


def main():
    import pinocchio as pin
    from scipy.interpolate import CubicSpline
    ap = argparse.ArgumentParser()
    ap.add_argument("--urdf", default=os.path.join(ROOT, "sim", "RTC-7", "RTC-7.urdf"))
    ap.add_argument("--traj", default=os.path.join(ROOT, "sim", "RTC-7", "RTC-7-demo-traj.csv"))
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--rate", type=float, default=500.0, help="Hz of the evaluation")
    ap.add_argument("--md", default=os.path.join(ROOT, "robot", "RTC-7-dynamics.md"))
    ap.add_argument("--png", default=os.path.join(ROOT, "robot", "RTC-7-dynamics.png"))
    ap.add_argument("--csv", default=os.path.join(ROOT, "sim", "RTC-7", "RTC-7-demo-torques-ref.csv"),
                    help="torques per sample (reference for the Simscape run, sim/RTC-7/rtc7_build.m)")
    a = ap.parse_args()
    head, D = read_csv(a.traj)
    t = D[:, 0] / a.speed
    Q = D[:, 1:]
    sp = CubicSpline(t, Q, axis=0, bc_type="clamped")
    ts = np.arange(0, t[-1], 1.0 / a.rate)
    q, dq, ddq = sp(ts), sp(ts, 1), sp(ts, 2)
    m = pin.buildModelFromUrdf(a.urdf)
    d = m.createData()
    m.gravity.linear[:] = [0, 0, -9.81]
    tau = np.array([pin.rnea(m, d, q[k], dq[k], ddq[k]) for k in range(len(ts))])
    grav = np.array([pin.computeGeneralizedGravity(m, d, q[k]) for k in range(len(ts))])
    names = [h.replace("_rad", "") for h in head[1:]]
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["t_s"] + [n + "_Nm" for n in names] + [n + "_grav_Nm" for n in names])
            for k in range(0, len(ts), max(1, int(a.rate / 100))):          # 100 Hz is enough to compare
                w.writerow([f"{ts[k] * a.speed:.3f}"] + [f"{v:.2f}" for v in tau[k]] + [f"{v:.2f}" for v in grav[k]])
    cards = card_torques(names)
    payload = sum(m.inertias[i].mass for i in range(len(m.inertias)))  # total for the record
    rows = []
    for i, nm in enumerate(names):
        k = int(np.argmax(np.abs(tau[:, i])))
        rows.append((nm, cards[i][0], np.abs(grav[:, i]).max(), abs(tau[k, i]), ts[k] * a.speed,
                     np.degrees(np.abs(dq[:, i])).max(), np.degrees(np.abs(ddq[:, i])).max(), cards[i][1], cards[i][2]))
    L = [f"# RTC-7: joint torques along the demo program, with accelerations (`python tools/robot_dynamics.py --speed {a.speed:g}`)",
         "",
         f"Inverse dynamics (Pinocchio RNEA) on `sim/RTC-7/RTC-7.urdf` (payload as exported, interface 4 kg), "
         f"trajectory `{os.path.relpath(a.traj, ROOT)}` at speed x{a.speed:g} ({t[-1]:.1f} s). Gravity + inertia + Coriolis of the links; "
         "NOT included: rotor inertia of the motors through the reducers, friction, cables.", "",
         "| Joint | Drive | Max gravity only, N·m | Max with dynamics, N·m | at t, s | Max speed, °/s | Max accel., °/s² | Rated (T_design) / start-stop, N·m | Peak, % of start-stop |",
         "|---|---|---|---|---|---|---|---|---|"]
    for nm, drv, g, tm, tk, v, acc, tr, ts_ in rows:
        L.append(f"| {nm} | {drv} | {g:.0f} | {tm:.0f} | {tk:.1f} | {v:.0f} | {acc:.0f} | {tr:.0f} / {ts_:.0f} | {100 * tm / ts_:.0f} % |")
    L += ["", "Start-stop torque is the catalog limit for acceleration / braking; the rated torque - for the "
          "average load over a cycle.", ""]
    os.makedirs(os.path.dirname(a.md), exist_ok=True)
    open(a.md, "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))
    if a.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ink, mute, line, lineg = "#1b2026", "#5d6670", "#2a5d9f", "#a9b1ba"
        fig, axs = plt.subplots(len(names), 1, figsize=(11, 1.55 * len(names) + 0.8), sharex=True)
        for i, ax in enumerate(axs):
            tr, tss = cards[i][1], cards[i][2]
            ax.plot(ts * a.speed, 100 * grav[:, i] / tss, color=lineg, lw=1.6, label="gravity only")
            ax.plot(ts * a.speed, 100 * tau[:, i] / tss, color=line, lw=2.0, label="with accelerations")
            for y, ls in ((100, "--"), (-100, "--"), (100 * tr / tss, ":"), (-100 * tr / tss, ":")):
                ax.axhline(y, color=mute, lw=0.9, ls=ls)
            ax.axhline(0, color="#d5d9de", lw=0.8)
            lim = max(110, 100 * np.abs(tau[:, i]).max() / tss * 1.1)
            ax.set_ylim(-lim, lim)
            ax.set_ylabel(f"{names[i]}\n{cards[i][0]}", rotation=0, ha="right", va="center", color=ink, fontsize=9)
            ax.tick_params(colors=mute, labelsize=8)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            for s in ("left", "bottom"):
                ax.spines[s].set_color("#c9cfd6")
            pk = rows[i][3]
            ax.text(1.0, 0.92, f"peak {pk:.0f} N·m = {100 * pk / tss:.0f} % of start-stop {tss:.0f}",
                    transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=ink)
        axs[0].legend(loc="upper left", fontsize=8.5, frameon=False, ncol=2)
        axs[-1].set_xlabel("program time, s", color=ink, fontsize=9)
        fig.suptitle(f"RTC-7: joint torque, % of the reducer start-stop torque (dashed ±100 %, dotted = rated); "
                     f"demo program x{a.speed:g}", fontsize=10.5, color=ink, x=0.01, ha="left")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        fig.savefig(a.png, dpi=130)
        print("plot ->", a.png)


if __name__ == "__main__":
    main()
