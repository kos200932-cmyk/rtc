#!/usr/bin/env python3
"""Joint loads of the model against the customer requirements (robot/RTC-7-joint-requirements.txt).

    python tools/joint_compare.py [--tacc 0.5 0.2] [--poses 20000] [--md robot/RTC-7-joint-compare.md]

Inverse dynamics on sim/RTC-7/RTC-7.urdf (Pinocchio). For every joint: torque about the axis, axial / radial
force and tilting moment at the centre of the output face (the wrench the joint passes from the distal side).
Cases:
  S   statics, the worst of N random poses in the joint ranges (payload as exported);
  P   the demo program retimed to n0 (tools/program_retime.py -> sim/RTC-7/RTC-7-n0-traj.csv);
  A   start / stop of the joint alone to n0 in t_acc s (constant acceleration n0 / t_acc, speed n0, the worst
      of N random poses and both signs) - the rated duty of a drive.
Power = |torque * speed|. NOT included: motor rotor inertia, friction, cables.
"""
import argparse
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import program_retime as pr  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AXES = [np.array(v, float) for v in ([0, 0, 1], [1, 0, 0], [0, 0, 1], [1, 0, 0], [0, 0, 1], [1, 0, 0], [0, 0, 1])]
FACE = [-35.0, 0.0, 228.0, -205.0, 159.5, 159.5, 161.0]   # output face centre on the axis from the joint frame, mm
LIM = np.radians([[-180, 180], [-94, 94], [-180, 180], [-171, 171], [-180, 180], [-180, 180], [-180, 180]])


class Model:
    def __init__(self, urdf):
        import pinocchio as pin
        self.pin = pin
        self.m = pin.buildModelFromUrdf(urdf)
        self.d = self.m.createData()
        self.m.gravity.linear[:] = [0, 0, -9.81]

    def loads(self, q, dq, ddq):
        """7 x 4: Fa, Fr, M_tilt, |torque| per joint, and the joint torques"""
        tau = self.pin.rnea(self.m, self.d, q, dq, ddq).copy()
        out = np.zeros((7, 4))
        for k in range(7):
            f = self.d.f[k + 1]
            a = AXES[k]
            F, M = np.array(f.linear), np.array(f.angular)
            Mo = M - np.cross(a * FACE[k] * 1e-3, F)
            out[k] = (abs(F @ a), np.linalg.norm(F - (F @ a) * a), np.linalg.norm(Mo - (Mo @ a) * a), abs(Mo @ a))
        return out, tau


def traj(path):
    from scipy.interpolate import CubicSpline
    with open(path, encoding="utf-8") as f:
        r = list(csv.reader(f))
    D = np.array([[float(x) for x in row] for row in r[1:]])
    sp = CubicSpline(D[:, 0], D[:, 1:], axis=0, bc_type="clamped")
    ts = np.arange(0, D[-1, 0], 1 / 100.0)
    return sp(ts), sp(ts, 1), sp(ts, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urdf", default=os.path.join(ROOT, "sim", "RTC-7", "RTC-7.urdf"))
    ap.add_argument("--req", default=os.path.join(ROOT, "robot", "RTC-7-joint-requirements.txt"))
    ap.add_argument("--traj", default=os.path.join(ROOT, "sim", "RTC-7", "RTC-7-n0-traj.csv"))
    ap.add_argument("--tacc", type=float, nargs="+", default=[0.5, 0.2], help="start time to n0, s")
    ap.add_argument("--poses", type=int, default=20000)
    ap.add_argument("--md", default=os.path.join(ROOT, "robot", "RTC-7-joint-compare.md"))
    a = ap.parse_args()
    req = pr.read_req(a.req)
    n0 = np.radians([r["n0"] for r in req])
    M = Model(a.urdf)
    z = np.zeros(7)
    rng = np.random.default_rng(3)
    poses = rng.uniform(LIM[:, 0], LIM[:, 1], size=(a.poses, 7))
    S = np.zeros((7, 4))
    for q in poses:
        S = np.maximum(S, M.loads(q, z, z)[0])
    Q, DQ, DDQ = traj(a.traj)
    P, Ppow, Pv = np.zeros((7, 4)), np.zeros(7), np.degrees(np.abs(DQ).max(0))
    for q, dq, ddq in zip(Q, DQ, DDQ):
        L, tau = M.loads(q, dq, ddq)
        P = np.maximum(P, L)
        Ppow = np.maximum(Ppow, np.abs(tau * dq))
    A = {}
    for ta in a.tacc:
        R = np.zeros((7, 4))
        for i in range(7):
            for q in poses[: a.poses // 4]:
                for sg in (1, -1):
                    dq, ddq = z.copy(), z.copy()
                    dq[i], ddq[i] = n0[i], sg * n0[i] / ta
                    L, _ = M.loads(q, dq, ddq)
                    R[i] = np.maximum(R[i], L[i])
        A[ta] = R
    # ---- report
    L = ["# RTC-7: joint loads of the model vs the requirements (`python tools/joint_compare.py`)", "",
         f"Requirements: `{os.path.relpath(a.req, ROOT)}` (customer table 2). Model: `sim/RTC-7/RTC-7.urdf`, "
         "inverse dynamics (Pinocchio). Forces and tilting moment - the wrench passed by the joint, at the centre of "
         "its output face. Cases: **S** statics, worst of "
         f"{a.poses} random poses; **P** demo program retimed to n0 (`robot/RTC-7-demo-n0.txt`, "
         f"`{os.path.relpath(a.traj, ROOT)}`); **A t** start / stop of the joint alone to n0 in t s, worst pose "
         "(n0 / t constant acceleration at speed n0). Not included: motor rotor inertia, friction, cables.", ""]
    cols = ["S", "P"] + [f"A {t:g}" for t in a.tacc]
    data = [S, P] + [A[t] for t in a.tacc]
    for title, j, key in (("Torque about the axis, N·m", 3, "M_nom"), ("Tilting moment, N·m", 2, "M_tilt"),
                          ("Radial force, N", 1, "Fr"), ("Axial force, N", 0, "Fa")):
        L += [f"## {title}", "", "| Joint | Size | Required | " + " | ".join(cols) + " | Max / required |",
              "|---|---|---|" + "---|" * len(cols) + "---|"]
        for k, r in enumerate(req):
            v = [D[k, j] for D in data]
            L.append(f"| {r['joint']} | {r['size']} | {r[key]:.0f} | " + " | ".join(f"{x:.0f}" for x in v)
                     + f" | {100 * max(v) / r[key]:.0f} % |")
        L.append("")
    L += ["## Speed and power", "", "| Joint | n0, °/s | P_nom, W | P: max speed, °/s | P: max power, W | "
          + " | ".join(f"A {t:g}: torque x n0, W" for t in a.tacc) + " | S: torque x n0, W |",
          "|---|---|---|---|---|" + "---|" * len(a.tacc) + "---|"]
    for k, r in enumerate(req):
        L.append(f"| {r['joint']} | {r['n0']:.0f} | {r['P_nom']:.0f} | {Pv[k]:.0f} | {Ppow[k]:.0f} | "
                 + " | ".join(f"{A[t][k, 3] * n0[k]:.0f}" for t in a.tacc) + f" | {S[k, 3] * n0[k]:.0f} |")
    L.append("")
    open(a.md, "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))
    js = {"cases": cols, "req": req, "loads": {c: D.round(1).tolist() for c, D in zip(cols, data)},
          "P_speed_deg": Pv.round(1).tolist(), "P_power_W": Ppow.round(1).tolist()}
    import json
    json.dump(js, open(os.path.splitext(a.md)[0] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
