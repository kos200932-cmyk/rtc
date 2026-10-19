#!/usr/bin/env python3
"""Clearance while a joint turns: the parts that move with the joint against the parts that do not.

    python tools/sweep_check.py --axis J2 --range 120 --step 2 \
        --fixed links/LINK-1/LINK-1.txt --moving links/LINK-2/LINK-2.txt [--layout robot/RTC-7-layout.txt]

Moving set: the given link specs + every joint after the axis joint (their real profiles, zero pose)
+ the rotating parts of the axis joint. Fixed set: the given link specs + the fixed parts of the axis
joint + the joints before it + the fixed ОПУ outer ring. The moving set is turned about the joint axis
from 0 to +range and to -range; the first angle with an overlap (> 1 mm3) on each side is reported.
"""
import argparse
import math
import os
import sys

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.Bnd import Bnd_Box
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import link_build as lb  # noqa: E402
import robot_scheme as rs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def box(s):
    b = Bnd_Box()
    BRepBndLib.Add_s(s, b)
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--axis", required=True)
    ap.add_argument("--range", type=float, default=120.0)
    ap.add_argument("--step", type=float, default=2.0)
    ap.add_argument("--fixed", nargs="*", default=[])
    ap.add_argument("--moving", nargs="*", default=[])
    ap.add_argument("--layout", default=os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    a = ap.parse_args()
    lay = rs.read_layout(a.layout)
    names = [x["name"] for x in lay["axes"]]
    k = names.index(a.axis)
    ax = lay["axes"][k]
    env = lb.envelope_solids(a.layout, [])
    fixed, moving = [], []
    for spec in a.fixed:
        for p in lb.parse(spec)[0]:
            fixed.append((p["name"], lb.build_part(p), "link"))
    for spec in a.moving:
        for p in lb.parse(spec)[0]:
            moving.append((p["name"], lb.build_part(p), "link"))
    for nm, sol, jn, kind in env:
        if jn == "base" or (jn in names and names.index(jn) < k):
            fixed.append((nm, sol, jn))
        elif jn == a.axis:
            if kind == "rot" and "OutputShaft" not in nm:
                continue  # input side of the axis joint turns inside its own housing
            (moving if kind == "rot" else fixed).append((nm, sol, jn))
        else:
            moving.append((nm, sol, jn))
    print(f"axis {a.axis}: point {ax['p']}, direction {ax['w']}; {len(moving)} moving / {len(fixed)} fixed bodies")
    fboxes = [box(s) for _, s, _ in fixed]
    # zero pose must be clear first
    res = {}
    for sign in (1, -1):
        first = None
        for th in np.arange(0, a.range + 1e-9, a.step):
            t = gp_Trsf()
            t.SetRotation(gp_Ax1(gp_Pnt(*ax["p"]), gp_Dir(*ax["w"])), math.radians(sign * th))
            hits = []
            for mn, ms, mj in moving:
                s2 = BRepBuilderAPI_Transform(ms, t, True).Shape()
                b2 = box(s2)
                for (fn, fs, fj), fb in zip(fixed, fboxes):
                    if mj == fj and mj != "link" or b2.IsOut(fb):
                        continue
                    v, _ = lb.volume(BRepAlgoAPI_Common(s2, fs).Shape())
                    if v > 1.0:
                        hits.append(f"{mn} x {fn} ({v:.0f} mm3)")
            if hits:
                first = (sign * th, hits)
                break
        res[sign] = first
        if first:
            print(f"{'+' if sign > 0 else '-'} side: first contact at {first[0]:+.0f} deg: " + "; ".join(first[1][:4]))
        else:
            print(f"{'+' if sign > 0 else '-'} side: free up to {sign * a.range:+.0f} deg")
    lo = (res[-1][0] + a.step) if res[-1] else -a.range
    hi = (res[1][0] - a.step) if res[1] else a.range
    print(f"free range of {a.axis}: {lo:+.0f} .. {hi:+.0f} deg (step {a.step:g})")


if __name__ == "__main__":
    main()
