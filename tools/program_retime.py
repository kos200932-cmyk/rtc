#!/usr/bin/env python3
"""Retime a motion program to the rated joint speeds n0 (robot/RTC-7-joint-requirements.txt).

    python tools/program_retime.py [--program robot/RTC-7-demo.txt] [--req robot/RTC-7-joint-requirements.txt]
                                   [--out robot/RTC-7-demo-n0.txt] [--traj sim/RTC-7/RTC-7-n0-traj.csv]

Same path, new durations: every MOVEJ / MOVEL gets the shortest duration at which no joint goes faster than its
n0 (the limiting joint reaches exactly n0 at the middle of the move; rounded up to 0.1 s). MOVEJ is a quintic
blend - peak speed 1.875 |dq| / T, peak acceleration 5.774 |dq| / T^2; MOVEL - the IK path is sampled and scaled.
WAIT / LABEL / GRIP / RELEASE are kept. Writes the new program (text, same format) and its joint trajectory
(rad, csv - input of tools/robot_dynamics.py --traj, and of the Simscape model).
"""
import argparse
import csv
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import robot_anim as ra  # noqa: E402
import robot_scheme as rs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_req(path):
    out = []
    for raw in open(path, encoding="utf-8"):
        t = raw.split("#", 1)[0].split()
        if t and t[0].upper() == "JOINT":
            out.append({"joint": t[1], "M_nom": float(t[2]), "n0": float(t[3]), "P_nom": float(t[4]), "size": t[5],
                        "M_tilt": float(t[6]), "Fr": float(t[7]), "Fa": float(t[8])})
    return out


def peak_speed_movel(lay, q, d, tool, n=150):
    """peak joint speeds (rad/s) of MOVEL d done in 1 s, and the end pose"""
    T0 = ra.tcp_T(lay, q, tool)
    Q = [q.copy()]
    for s in ra.s_curve(n):
        T = T0.copy()
        T[:3, 3] = T0[:3, 3] + np.array(d) * s
        q = ra.ik_step(lay, q, T, tool)
        Q.append(q.copy())
    Q = np.array(Q)
    return np.abs(np.diff(Q, axis=0)).max(0) * n, q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    ap.add_argument("--program", default=os.path.join(ROOT, "robot", "RTC-7-demo.txt"))
    ap.add_argument("--req", default=os.path.join(ROOT, "robot", "RTC-7-joint-requirements.txt"))
    ap.add_argument("--out", default=os.path.join(ROOT, "robot", "RTC-7-demo-n0.txt"))
    ap.add_argument("--traj", default=os.path.join(ROOT, "sim", "RTC-7", "RTC-7-n0-traj.csv"))
    a = ap.parse_args()
    lay = rs.read_layout(a.layout)
    prg = ra.read_program(a.program)
    n0 = np.radians([r["n0"] for r in read_req(a.req)])
    q = np.radians(prg["start"])
    new, report = [], []
    for st in prg["steps"]:
        if st[0] in ("MOVEJ", "MOVEL"):
            kind, dur, args = st
            if kind == "MOVEJ":
                q1 = np.radians(args[:7])
                v1 = 1.875 * np.abs(q1 - q)                     # peak speed at T = 1 s
            else:
                v1, q1 = peak_speed_movel(lay, q, args[:3], prg["tool"])
            r = v1 / n0
            T = max(0.5, math.ceil(r.max() * 10 - 1e-9) / 10)
            lim = int(np.argmax(r))
            report.append((kind, dur, T, f"J{lim + 1}", np.degrees(v1 / T)))
            new.append((kind, T, args))
            q = q1
        else:
            new.append(st)
    # write the program (header + the retimed steps)
    head = [ln for ln in open(a.program, encoding="utf-8") if ln.startswith("#")]
    L = head + [f"# RETIMED by tools/program_retime.py to the rated speeds n0 of {os.path.relpath(a.req, ROOT)}: "
                + ", ".join(f"J{i + 1} {math.degrees(v):.0f}" for i, v in enumerate(n0)) + " deg/s\n",
                f"PROGRAM {prg['name']}-n0\n", f"FPS     {prg['fps']}\n", f"TOOL    {prg['tool']:g}\n",
                "START   " + " ".join(f"{v:g}" for v in prg["start"]) + "\n", "\n"]
    for st in new:
        if st[0] == "LABEL":
            L.append(f"LABEL   {st[1]}\n")
        elif st[0] in ("GRIP", "RELEASE"):
            L.append(st[0] + "\n")
        else:
            L.append(f"{st[0]:<7} {st[1]:<5g} " + " ".join(f"{v:g}" for v in st[2]) + "\n")
    L.append("END\n")
    open(a.out, "w", encoding="utf-8").writelines(L)
    tot0 = sum(s[1] for s in prg["steps"] if s[0] in ("MOVEJ", "MOVEL", "WAIT"))
    tot1 = sum(s[1] for s in new if s[0] in ("MOVEJ", "MOVEL", "WAIT"))
    print(f"program -> {a.out}: {tot0:.1f} s -> {tot1:.1f} s")
    for kind, d0, d1, lim, v in report:
        print(f"  {kind}  {d0:4.1f} -> {d1:5.1f} s  limited by {lim}; peak speeds, deg/s: "
              + " ".join(f"{x:5.1f}" for x in v))
    prg2 = ra.read_program(a.out)
    frames, _ = ra.trajectory(lay, prg2)
    os.makedirs(os.path.dirname(a.traj), exist_ok=True)
    with open(a.traj, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s"] + [ax["name"] + "_rad" for ax in lay["axes"]])
        for k, qq in enumerate(frames):
            w.writerow([f"{k / prg2['fps']:.5f}"] + [f"{v:.6f}" for v in qq])
    print(f"trajectory -> {a.traj}: {len(frames)} frames")


if __name__ == "__main__":
    main()
