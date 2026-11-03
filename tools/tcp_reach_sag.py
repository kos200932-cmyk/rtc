#!/usr/bin/env python3
"""TCP deflection (rigid joints, link compliances fea/stiffness/compliance.json) over the poses with the TCP at a given
horizontal distance from the J1 axis: planar arm (J1 = J3 = J5 = J7 = 0), J2 / J4 / J6 solved for the TCP height and the
gripper direction (down / horizontal outward).   python tools/tcp_reach_sag.py [--r 1500] [--h0 -600 --h1 2000 --dh 100]"""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.optimize import least_squares
import tcp_stiffness as ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r", type=float, default=1500.0)
    ap.add_argument("--h0", type=float, default=-600.0); ap.add_argument("--h1", type=float, default=2400.0)
    ap.add_argument("--dh", type=float, default=100.0)
    ap.add_argument("--pay-off", type=float, default=200.0)
    a = ap.parse_args()
    A = ts.Arm(os.path.join(ts.ROOT, "fea", "stiffness"), pay_off=a.pay_off)
    # reach direction of the planar arm: horizontal, from the J1 axis to the zero-pose J3 axis
    n = A.arm.axes[1][1] / np.linalg.norm(A.arm.axes[1][1])          # J2 axis (horizontal): the arm moves in the plane across it
    hd = np.cross(np.array([1.0, 0, 0]), n); hd /= np.linalg.norm(hd)
    if A.tcp([0, 90, 0, 0, 0, 0, 0])[0] @ hd < 0:
        hd = -hd
    rows = []
    for mode, app in (("down", np.array([-1.0, 0, 0])), ("out", hd)):
        seed = np.array([60.0, 60.0, 30.0])
        for h in np.arange(a.h0, a.h1 + 1, a.dh):
            def res(x):
                q = [0, x[0], 0, x[1], 0, x[2], 0]; p, ap_ = A.tcp(q)
                return np.r_[p[0] - h, np.hypot(p[1], p[2]) - a.r, 500 * (ap_ - app)]
            best = None                                   # within the joint ranges: J2 +-90 (mounting plane), J4 +-170
            for s in (seed, np.array([60, 60, 0.]), np.array([-30, 100, -60.]), np.array([80, 100, 90.]), np.array([-60, 80, -150.]), np.array([20, 130, 60.])):
                r = least_squares(res, s, bounds=([-90, -170, -360], [90, 170, 360]), xtol=1e-9, ftol=1e-9, max_nfev=300)
                if best is None or r.cost < best.cost:
                    best = r
            if np.linalg.norm(res(best.x)[:2]) > 1.0 or np.linalg.norm(res(best.x)[2:]) > 5:
                continue
            seed = best.x
            q = [0, best.x[0], 0, best.x[1], 0, best.x[2], 0]
            d, parts = A.deflection(q, parts=True)
            rows.append((mode, h, q, d, parts))
            print(f"{mode:4s} h {h:6.0f}  J2 {q[1]:6.1f} J4 {q[3]:6.1f} J6 {q[5]:6.1f}  TCP sag {-d[0]:5.2f} mm |d| {np.linalg.norm(d):5.2f}  "
                  + " ".join(f"{k} {np.linalg.norm(v):.2f}" for k, v in parts.items()), flush=True)
    L = [f"# TCP deflection at {a.r:.0f} mm from the J1 axis, rigid joints - `python tools/tcp_reach_sag.py --r {a.r:.0f}`", "",
         "Planar arm (J1 = J3 = J5 = J7 = 0; J2 within +-90, J4 within +-170), gripper down or horizontal outward; payload 8 kg",
         f"{a.pay_off:g} mm beyond the TCP along the gripper + SZU 4 kg; link compliances fea/stiffness/compliance.json (CalculiX).", "",
         "| gripper | TCP height, mm | J2 / J4 / J6, deg | sag (vertical), mm | total, mm | link 1 | link 2 | link 3 | link 4 | link 5 | ОПУ |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for mode, h, q, d, parts in rows:
        L.append(f"| {mode} | {h:.0f} | {q[1]:.0f} / {q[3]:.0f} / {q[5]:.0f} | {-d[0]:.2f} | {np.linalg.norm(d):.2f} | "
                 + " | ".join(f"{np.linalg.norm(parts[k]):.2f}" for k in ("L1", "L2", "L3", "L4", "L5", "OPU")) + " |")
    open(os.path.join(ts.ROOT, "fea", "stiffness", f"reach{a.r:.0f}.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return rows


if __name__ == "__main__":
    main()
