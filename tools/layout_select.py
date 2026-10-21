#!/usr/bin/env python3
"""Reducer choice for the joints of the arm with the axes of robot/RTC-7-layout.txt kept (new joint line-up).

    python tools/layout_select.py [--payload 8] [--interface 4] [--share 0.6] [--speed 0.2] [--accel 0.1]
                                  [--fix J2=80E] [--use 0.9] [--current] [--reach 0] [--md robot/RTC-7-layout-v2.md]

Mass model: the designed links links/LINK-n (as tools/robot_statics.py) + every joint J2..J7 with the mass
m_reducer / share (the reducer is `share` of the joint mass), split housing+motor / output shaft and placed as
in the present joint of that axis; interface (4 kg, 30 mm beyond the flange) + payload (100 mm beyond).
Loads per joint - inverse dynamics (Pinocchio, point masses): torque about the axis, tilting moment and axial /
radial force at the output face. Worst case over random poses in the joint ranges, gravity + all joints at
+-speed rad/s and +-accel rad/s^2 (random signs). --reach R: only poses with the payload within R mm of the J1
axis (reduced zone).
Choice: top-down, the lightest KB (loaded to <= --use of its ratings) of components/DMRD/KB-series.txt with T_rated >= torque, M_tilt >= tilting
moment, F_axial >= axial force (J1: torque only - the arm stands on the ОПУ, checked separately); fixed joints
by --fix. Iterated until the line-up does not change (the joint masses load the joints below).
Motor: the lightest of the T-motor cards (RI frameless; J2 - the AK80-9 actuator with its 9:1) and the ratio,
for which T_motor_rated x ratio x eta >= torque and n_rated >= output speed x ratio.
--current: the present joints with their own masses (check against robot/RTC-7-joint-compare.md).
"""
import argparse
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_envelope as je  # noqa: E402
import robot_scheme as rs  # noqa: E402
import robot_statics as st  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIM = np.radians([[-180, 180], [-94, 94], [-180, 180], [-171, 171], [-180, 180], [-180, 180], [-180, 180]])
KB_RATIOS = [21, 29, 49, 59, 79, 99, 119, 159]
E_RATIOS = [81, 101, 121, 153]
CUR = {"SHM-60": "KB25", "SHM-150": "KB32", "SHM-500": "KB45", "SHM-1000": "80E", "SHM-150m": "KB32"}
MOTORS = ["RI70-KV95", "RI80-V2-KV75", "RI115-PH-KV40"]


def read_catalog(path):
    out = {}
    for raw in open(path, encoding="utf-8"):
        t = raw.split("#", 1)[0].split()
        if t and t[0] == "RED":
            out[t[1]] = {"name": t[1], "T": float(t[3]), "Fa": float(t[4]), "Mt": float(t[5]), "Tpk": float(t[6]),
                         "Tss": float(t[7]), "mass": float(t[9])}
    return out


def motor(name):
    d = st.card_data(os.path.join(ROOT, "components", "T-motor", name, name + ".txt"))
    return {"name": name, "T": float(d["T_rated"]), "Tpk": float(d["T_peak"]), "n": float(d["n_rated"]),
            "mass": float(d["mass"]), "pre": float(d.get("ratio", 1))}


class Arm:
    def __init__(self, lay, red, share, payload, iface, tool=100.0, current=False, jmass=None):
        import pinocchio as pin
        self.pin, self.lay = pin, lay
        ax = lay["axes"]
        self.n = len(ax)
        env = je.all_joints()
        B = []
        self.jmass = []
        for i, a in enumerate(ax):
            mf, xf, mo, xo, _ = st.joint_masses(a["joint"].rstrip("m"))
            M = (mf + mo) if current else (jmass or {}).get(i, red[i]["mass"] / share)
            self.jmass.append(M)
            if i == 0:
                continue                       # J1 under the ОПУ: housing on the base
            s = M / (mf + mo)
            e = env[a["joint"]]
            md = np.zeros(3)
            md["XYZ".index(a["motor"][1])] = 1 if a["motor"][0] == "+" else -1
            B.append((mf * s, a["face"] - md * (xf - e["x_out"]), i))
            B.append((mo * s, a["face"] - md * (xo - e["x_out"]), i + 1))
        for m, c, k, _ in st.real_link_bodies():
            B.append((m, c, k))
        f = lay["flange"]
        B.append((iface, f["p"] + f["w"] * 30.0, self.n))
        self.pay_i = len(B)
        B.append((payload, f["p"] + f["w"] * tool, self.n))
        self.B = B
        m = pin.Model()
        parent, prev = 0, np.zeros(3)
        for i, a in enumerate(ax):
            jid = m.addJoint(parent, pin.JointModelRevoluteUnaligned(a["w"]), pin.SE3(np.eye(3), (a["p"] - prev) * 1e-3),
                             a["name"])
            parent, prev = jid, a["p"]
        for mm, c, k in B:
            if k == 0 or mm <= 0:
                continue
            o = ax[k - 1]["p"]
            m.appendBodyToJoint(k, pin.Inertia(mm, (c - o) * 1e-3, np.eye(3) * 1e-6), pin.SE3.Identity())
        m.gravity.linear[:] = [0, 0, -9.81]
        self.m, self.d = m, m.createData()
        self.face = [(a["face"] - a["p"]) * 1e-3 for a in ax]
        self.w = [a["w"] / np.linalg.norm(a["w"]) for a in ax]

    def loads(self, q, dq, ddq):
        """n x 4: torque, tilting moment, axial, radial at the output face"""
        self.pin.rnea(self.m, self.d, q, dq, ddq)
        out = np.zeros((self.n, 4))
        for k in range(self.n):
            f = self.d.f[k + 1]
            F, M = np.array(f.linear), np.array(f.angular)
            a = self.w[k]
            Mo = M - np.cross(self.face[k], F)
            out[k] = (abs(Mo @ a), np.linalg.norm(Mo - (Mo @ a) * a), abs(F @ a), np.linalg.norm(F - (F @ a) * a))
        return out

    def payload_r(self, q):
        """distance of the payload from the J1 axis, mm"""
        _, _, T = rs.fk_poe(self.lay, q)
        f = self.lay["flange"]
        p = T[:3, :3] @ (f["w"] * 100.0) + T[:3, 3]
        return math.hypot(p[0], p[1]), p[2]


def worst(arm, speed, accel, n, reach=0.0, seed=5):
    rng = np.random.default_rng(seed)
    W = np.zeros((arm.n, 4))
    pose = [None] * arm.n
    for _ in range(n):
        q = rng.uniform(LIM[:, 0], LIM[:, 1])
        if reach and arm.payload_r(q)[0] > reach:
            continue
        for _s in range(2):
            dq = speed * rng.choice([-1, 1], arm.n)
            ddq = accel * rng.choice([-1, 1], arm.n)
            L = arm.loads(q, dq, ddq)
            for k in range(arm.n):
                if L[k, 0] > W[k, 0]:
                    pose[k] = q.copy()
            W = np.maximum(W, L)
    # local refinement of the torque peak of every joint (gravity dominated)
    for k in range(arm.n):
        if pose[k] is None:
            continue
        q, best = pose[k].copy(), W[k, 0]
        for step in np.radians([8, 3, 1]):
            for _ in range(60):
                qq = np.clip(q + rng.normal(0, step, arm.n), LIM[:, 0], LIM[:, 1])
                if reach and arm.payload_r(qq)[0] > reach:
                    continue
                L = arm.loads(qq, speed * np.sign(rng.normal(size=arm.n)), accel * np.sign(rng.normal(size=arm.n)))
                W = np.maximum(W, L)
                if L[k, 0] > best:
                    q, best = qq, L[k, 0]
        pose[k] = q
    return W, pose


def choose(cat, L, k, fixed, use=1.0):
    if k in fixed:
        return cat[fixed[k]]
    kb = sorted([r for r in cat.values() if r["name"].startswith("KB")], key=lambda r: r["mass"])
    for r in kb:
        if use * r["T"] >= L[0] and (k == 0 or (use * r["Mt"] >= L[1] and use * r["Fa"] >= L[2])):
            return r
    return kb[-1]


def pick_motor(k, red, T, speed, eta, use=1.0):
    n_out = speed * 60 / (2 * math.pi)
    names = ["AK80-9-V3-KV100"] if red["name"] == "80E" else MOTORS
    ratios = E_RATIOS if red["name"] == "80E" else KB_RATIOS
    best = None
    for nm in names:
        mo = motor(nm)
        for i in ratios:
            ok_t = mo["T"] * i * eta * use >= T
            ok_n = mo["n"] >= n_out * i            # n_rated of a geared actuator (AK80-9) is after its 9:1
            if ok_t and ok_n:
                best = (mo, i, T / (i * eta), n_out * i)
                break
        if best:
            break
    if not best:                                   # none is enough: the strongest, highest ratio, flagged
        mo = motor(names[-1])
        i = ratios[-1]
        best = (mo, i, T / (i * eta), n_out * i)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    ap.add_argument("--catalog", default=os.path.join(ROOT, "components", "DMRD", "KB-series.txt"))
    ap.add_argument("--payload", type=float, default=8.0)
    ap.add_argument("--interface", type=float, default=4.0)
    ap.add_argument("--share", type=float, default=0.6)
    ap.add_argument("--speed", type=float, default=0.2)
    ap.add_argument("--accel", type=float, default=0.1)
    ap.add_argument("--eta", type=float, default=0.8)
    ap.add_argument("--use", type=float, default=0.9, help="max share of the catalog rating used (margin)")
    ap.add_argument("--fix", nargs="*", default=["J2=80E"])
    ap.add_argument("--jmass", nargs="*", default=["J2=25.08"],
                    help="known joint masses, kg (J2: 80E 23 + AK80-9 0.48 + shafts / plates 1.6, user 2026-10-21)")
    ap.add_argument("--poses", type=int, default=6000)
    ap.add_argument("--reach", type=float, default=0.0)
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--md")
    a = ap.parse_args()
    lay = rs.read_layout(a.layout)
    cat = read_catalog(a.catalog)
    fixed = {int(s.split("=")[0][1:]) - 1: s.split("=")[1] for s in a.fix}
    jmass = {int(s.split("=")[0][1:]) - 1: float(s.split("=")[1]) for s in a.jmass}
    n = len(lay["axes"])
    sel = [cat[CUR[x["joint"]]] for x in lay["axes"]]
    for it in range(6):
        arm = Arm(lay, sel, a.share, a.payload, a.interface, current=a.current, jmass=jmass)
        W, pose = worst(arm, a.speed, a.accel, a.poses, a.reach)
        if a.current:
            break
        new = [choose(cat, W[k], k, fixed, a.use) for k in range(n)]
        print(f"iteration {it + 1}: " + " ".join(f"J{k + 1}={r['name']}" for k, r in enumerate(new)))
        if [r["name"] for r in new] == [r["name"] for r in sel]:
            break
        sel = new
    rows = []
    for k in range(n):
        r = sel[k]
        mo, i, Tm, nm = pick_motor(k, r, W[k, 0], a.speed, a.eta, a.use)
        rows.append((k, r, W[k], arm.jmass[k], mo, i, Tm, nm, arm.payload_r(pose[k]) if pose[k] is not None else (0, 0)))
    tot = sum(m for m, c, kk in arm.B) - a.payload
    L = []
    hdr = ("current joints, own masses" if a.current else
           f"reducer = {a.share * 100:.0f} % of the joint mass; known: {', '.join(a.jmass) or '-'} kg")
    L += [f"# RTC-7: joint line-up with the axes kept ({hdr}) - `python tools/layout_select.py"
          + (" --current" if a.current else "") + (f" --reach {a.reach:g}" if a.reach else "") + "`", "",
          f"Payload {a.payload:g} kg (100 mm beyond the flange) + interface {a.interface:g} kg; all joints at "
          f"±{a.speed:g} rad/s, ±{a.accel:g} rad/s²; worst of {a.poses} random poses in the joint ranges"
          + (f", payload within {a.reach:.0f} mm of the J1 axis" if a.reach else "") +
          f". Reducer loaded to <= {a.use * 100:.0f} % of T_rated / M_tilt / F_axial. Catalog `{os.path.relpath(a.catalog, ROOT)}`; fixed: {', '.join(a.fix) or '-'}. Motor: rated torque x ratio x "
          f"eta {a.eta:g} (loaded to <= {a.use * 100:.0f} % too). Moving mass (without payload, J1 excluded): {tot:.1f} kg.", "",
          "| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | "
          "Motor | Ratio | Motor torque, N·m (rated) | Motor speed, rpm (AK80-9: after its 9:1) | Worst pose: payload r / z, mm |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r, w, jm, mo, i, Tm, nm, (pr, pz) in rows:
        pct = lambda v, lim: f"{v:.0f} ({lim:.0f}, {100 * v / lim:.0f} %)" if lim else f"{v:.0f} (-)"
        tilt = pct(w[1], r["Mt"]) if k else f"{w[1]:.0f} (ОПУ)"
        fa = pct(w[2], r["Fa"]) if k else f"{w[2]:.0f} (ОПУ)"
        motor_t = f"{Tm:.2f} ({mo['T']:g} x{mo['pre']:g})" if mo["pre"] > 1 else f"{Tm:.2f} ({mo['T']:g})"
        L.append(f"| J{k + 1} | {r['name']} | {jm:.1f} | {pct(w[0], r['T'])} | {tilt} | {fa} | {w[3]:.0f} | {mo['name']} | "
                 f"{i} | {motor_t} | {nm:.0f} | {pr:.0f} / {pz:.0f} |")
    C0, Dp = 135e3, 0.178
    P0 = W[0, 3] + 2 * W[0, 1] / Dp + 0.44 * W[0, 2]
    L += ["", f"J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = {P0 / 1e3:.1f} kN against C0 135 kN (s0 = {C0 / P0:.1f}).", ""]
    txt = "\n".join(L)
    print(txt)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(txt + "\n")
    import json
    js = {"payload": a.payload, "interface": a.interface, "share": a.share, "speed": a.speed, "accel": a.accel,
          "reach": a.reach, "current": a.current,
          "joints": [{"joint": f"J{k + 1}", "reducer": r, "mass": jm, "torque": w[0], "tilt": w[1], "Fa": w[2], "Fr": w[3],
                      "motor": mo["name"], "motor_T": mo["T"], "pre": mo["pre"], "ratio": i, "Tm": Tm, "n_motor": nm}
                     for k, r, w, jm, mo, i, Tm, nm, _ in rows],
          "P0": P0, "moving_mass": tot}
    if a.md:
        json.dump(js, open(os.path.splitext(a.md)[0] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1,
                  default=float)


if __name__ == "__main__":
    main()
