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
    tcp0, _ = A.tcp([0] * 7); o3, _ = A.arm.axes[2]
    hd = np.array([0, o3[1], o3[2]]); hd /= np.linalg.norm(hd)
    rows = []
    for mode, app in (("down", np.array([-1.0, 0, 0])), ("out", hd)):
        seed = np.array([60.0, 60.0, 30.0])
        for h in np.arange(a.h0, a.h1 + 1, a.dh):
            target = np.array([h, *(hd[1:] * a.r)])
            def res(x):
                q = [0, x[0], 0, x[1], 0, x[2], 0]; p, ap_ = A.tcp(q)
                return np.r_[p - target, 500 * (ap_ - app)]
            best = None
            for s in (seed, np.array([90, 90, 0.]), np.array([30, 120, -60.]), np.array([-30, 150, 60.]), np.array([100, 30, 40.])):
                r = least_squares(res, s, xtol=1e-9, ftol=1e-9, max_nfev=300)
                if best is None or r.cost < best.cost:
                    best = r
            if np.linalg.norm(res(best.x)[:3]) > 1.0 or np.linalg.norm(res(best.x)[3:]) > 5:
                continue
            seed = best.x
            q = [0, best.x[0], 0, best.x[1], 0, best.x[2], 0]
            d, parts = A.deflection(q, parts=True)
            rows.append((mode, h, q, d, parts))
            print(f"{mode:4s} h {h:6.0f}  J2 {q[1]:6.1f} J4 {q[3]:6.1f} J6 {q[5]:6.1f}  TCP sag {-d[0]:5.2f} mm |d| {np.linalg.norm(d):5.2f}  "
                  + " ".join(f"{k} {np.linalg.norm(v):.2f}" for k, v in parts.items()), flush=True)
    return rows


if __name__ == "__main__":
    main()
