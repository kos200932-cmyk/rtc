#!/usr/bin/env python3
"""Static (gravity) torques in the joints of the arm for the layout robot/RTC-7-layout.txt.

    python tools/robot_statics.py robot/RTC-7-layout.txt [--payload 5] [--tool 100] [--eta 0.8]
                                  [--md robot/RTC-7-statics.md] [--png robot/RTC-7-torques.png]

Mass model (zero pose, then moved with the joints):
  * joints: reducer parts (MASS from the reducer card), motor (card DATA mass), designed parts
    (volume x density: aluminium 2700, couplings / keys / clamp flanges steel 7850); housing + motor
    belong to the previous link, the output shaft to the next one; centres of mass from the profiles;
  * links: ASSUMED aluminium tubes for the long links + end fittings (see LINKS below);
  * payload at the flange, its centre of mass --tool mm beyond the flange along the flange axis.
Gravity along -Z. For every joint the worst pose is searched (random poses + local refinement over
J2..J7, all angles allowed - no joint limits yet). Torques are compared with the reducer catalog
(rated / start-stop) and turned into the reducer ratio the motor needs (motor rated torque x eta).
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
import spec_preview as sp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = 9.81
AL, ST = 2700.0, 7850.0

# ASSUMED link structure (to be replaced by the real link geometry later):
#   tube: aluminium, OD x wall, along the link column; fitting: kg at each end
LINKS = {
    2: {"fitting": 2.0},                                  # J2 output -> J3 housing: bracket
    3: {"tube": (120, 5), "fitting": 1.5},                # upper arm J3 -> J4
    4: {"fitting": 1.5},                                  # J4 output -> J5 housing: bracket
    5: {"tube": (100, 4), "fitting": 1.0},                # forearm J5 -> J6
    6: {"fitting": 0.8},                                  # J6 output -> J7 housing: bracket
}


def card_data(path):
    d = {}
    for raw in open(path, encoding="utf-8"):
        t = re.split(r"#", raw, maxsplit=1)[0].split()
        if t and t[0] == "DATA":
            d.update(kv.split("=", 1) for kv in t[1:] if "=" in kv)
    return d


def part_com_x(p):
    """Axial centre of mass of a revolved profile (Pappus)."""
    pts = p["pts"]
    A = Sx = 0.0
    for i in range(len(pts)):          # integrate x*y and y over the area (solid of revolution)
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
        c = x1 * y2 - x2 * y1
        A += c * (y1 + y2)
        Sx += c * (x1 * (2 * y1 + y2) + x2 * (y1 + 2 * y2))
    return Sx / (2 * A) if A else sum(x for x, _ in pts) / len(pts)


def joint_masses(name):
    """(m_fixed, x_fixed, m_out, x_out_com, notes) in the joint frame."""
    jp = os.path.join(ROOT, "joints", name, name + ".txt")
    j = je.read_joint(jp)
    notes = []
    red = os.path.join(ROOT, j["use"]["reducer"])
    rd = card_data(red)
    _, rparts, _ = sp.parse(red)
    parts = [(p, "red") for p in rparts]
    if j["parts"]:
        parts += [(p, "des") for p in sp.parse(os.path.join(j["dir"], j["parts"]))[1]]
    mf = mfx = mo = mox = 0.0
    if rd.get("mass", "?") == "?":       # 80E: no catalog mass -> steel volume x 0.6 (internals are solid)
        vol = sum(sp.volume(p) for p in rparts)
        est = vol * ST * 0.6
        notes.append(f"{name}: reducer mass not in the catalog, ESTIMATED {est:.1f} kg (steel x 0.6)")
        for p in rparts:
            p["mass"] = est * sp.volume(p) / vol
    for p, kind in parts:
        if not p["pts"]:
            continue
        if p.get("mass"):
            m = p["mass"]
        else:
            rho = ST if re.search(r"Coupling|Key|ClampFlange", p["name"]) else AL
            m = sp.volume(p) * rho
        x = part_com_x(p) if not p.get("box") else (p["box"]["x0"] + p["box"]["x1"]) / 2
        if p["name"].endswith("OutputShaft"):
            mo += m
            mox += m * x
        else:
            mf += m
            mfx += m * x
    md = card_data(os.path.join(ROOT, j["use"]["motor"]))
    mm = float(md["mass"])
    xp, flip = j["place"].get("motor", (0.0, False))
    env = je.motor_envelope(os.path.join(ROOT, j["use"]["motor"]), xp, flip)
    xm = (env[0][0] + env[0][1]) / 2
    mf += mm
    mfx += mm * xm
    return mf, mfx / mf, mo, mox / mo if mo else 0.0, notes


IFACE = {"mass": 4.0, "com": 30.0}     # tool-change interface on J7 (user: 4 kg); COM ASSUMED 30 mm beyond the flange


def bodies(lay, payload, tool):
    """List of (mass kg, point at zero pose [mm], link index the body moves with)."""
    env = je.all_joints()
    out, notes = [], []
    ax = lay["axes"]
    for i, a in enumerate(ax):
        if i == 0:
            continue                    # J1: under the ОПУ, does not load the joints
        e = env[a["joint"]]
        mf, xf, mo, xo, nn = joint_masses(a["joint"])
        notes += nn
        md = np.zeros(3)
        md["XYZ".index(a["motor"][1])] = 1 if a["motor"][0] == "+" else -1
        u = -md
        out.append((mf, a["face"] + u * (xf - e["x_out"]), i, f"J{i + 1} housing+motor"))
        out.append((mo, a["face"] + u * (xo - e["x_out"]), i + 1, f"J{i + 1} output shaft"))
    # links (ASSUMED)
    face = {i: ax[i]["face"] for i in range(1, len(ax))}
    for k, spec in LINKS.items():
        # link k: from the output face of joint k (index k-1 -> J(k)) to the next joint (index k)
        a0 = face[k - 1] if k - 1 in face else ax[k - 1]["p"]
        a1 = ax[k]["face"]
        nxt = ax[k]
        e1 = env[nxt["joint"]]
        md = np.zeros(3)
        md["XYZ".index(nxt["motor"][1])] = 1 if nxt["motor"][0] == "+" else -1
        base1 = a1 + (-md) * (e1["x_base"] - e1["x_out"])        # mounting face of the next joint
        if "tube" in spec:
            od, wall = spec["tube"]
            # column along the previous roll axis from its output face up to the next pitch axis
            p0 = a0
            p1 = np.array([a0[0], a0[1], nxt["p"][2]])
            L = np.linalg.norm(p1 - p0)
            m = math.pi * ((od / 2) ** 2 - (od / 2 - wall) ** 2) * L * 1e-9 * AL
            out.append((m, (p0 + p1) / 2, k, f"link {k} tube D{od}x{wall}, {L:.0f} mm"))
            out.append((spec["fitting"], p0, k, f"link {k} fitting (low)"))
            out.append((spec["fitting"], base1, k, f"link {k} fitting (high)"))
        else:
            out.append((spec["fitting"], (a0 + base1) / 2, k, f"link {k} bracket"))
    if IFACE["mass"]:
        out.append((IFACE["mass"], lay["flange"]["p"] + lay["flange"]["w"] * IFACE["com"], len(ax),
                    "tool interface"))
    if payload:
        out.append((payload, lay["flange"]["p"] + lay["flange"]["w"] * tool, len(ax), "payload"))
    return out, notes


def torques(lay, bl, q, signed=False):
    """Gravity torque about every axis (N*m) at pose q."""
    pts, dirs, _ = rs.fk_poe(lay, q)
    Ts = lay["_Ts"]
    T_all = Ts + [Ts[-1] @ rs.screw_T(lay["axes"][-1]["w"], lay["axes"][-1]["p"], q[-1])]
    pos = [(T_all[k] @ np.r_[p, 1])[:3] * 1e-3 for m, p, k, _ in bl]
    tau = []
    for i in range(len(pts)):
        f = np.zeros(3)
        for (m, p, k, _), r in zip(bl, pos):
            if k >= i + 1:   # bodies moved by joint i (link i and further)
                f += np.cross(r - pts[i] * 1e-3, np.array([0, 0, -m * G]))
        tau.append(f @ dirs[i] if signed else abs(f @ dirs[i]))
    return np.array(tau)


def capacity_map(lay, b0, b1, rated, png, payload, step=(5, 6, 15)):
    """Payload the arm can hold statically at the reducer rated torques, over the reach plane.
    Poses in the plane of the arm (J1 = J3 = J5 = J7 = 0; J2, J4, J6 on a grid); the cell keeps the best
    pose (the controller may choose the configuration). Returns (r, z, capacity) arrays."""
    n = len(lay["axes"])
    R = np.array(rated)
    rows = []
    for q2 in np.arange(-150, 151, step[0]):
        for q4 in np.arange(-170, 171, step[1]):
            for q6 in np.arange(-135, 136, step[2]):
                q = np.radians([0, q2, 0, q4, 0, q6, 0])
                t0 = torques(lay, b0, q, signed=True)
                t1 = torques(lay, b1, q, signed=True) - t0
                cap = np.inf
                for i in range(1, n):
                    if abs(t0[i]) > R[i]:
                        cap = -1
                        break
                    if abs(t1[i]) > 1e-9:   # |t0 + P t1| <= R  ->  P <= (R - sign*t0)/|t1|
                        cap = min(cap, (R[i] - np.sign(t1[i]) * t0[i]) / abs(t1[i]))
                _, _, Tf = rs.fk_poe(lay, q)
                f = Tf[:3, 3]
                if f[2] < -100:
                    continue                 # below the base plane
                rows.append((np.hypot(f[0], f[1]), f[2], cap))
    A = np.array(rows)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cell = 50.0
    rmax, zmin, zmax = A[:, 0].max(), -100, A[:, 1].max()
    nr, nz = int(rmax // cell) + 1, int((zmax - zmin) // cell) + 1
    Gm = np.full((nz, nr), np.nan)
    for r, z, c in A:
        i, j = int((z - zmin) // cell), int(r // cell)
        c = min(c, 30)
        Gm[i, j] = c if np.isnan(Gm[i, j]) else max(Gm[i, j], c)
    fig, ax = plt.subplots(figsize=(8.5, 8))
    from matplotlib.colors import BoundaryNorm, ListedColormap
    bounds = [-1, 0, 2, 4, 6, 8, 10, 15, 30]
    cmap = ListedColormap(["#d9d9d6", "#fde0c5", "#f9b98c", "#f0904f", "#d9682a",
                           "#9fd3b8", "#4fb38a", "#1b8a5e"])
    im = ax.imshow(Gm, origin="lower", extent=(0, nr * cell, zmin, zmin + nz * cell), cmap=cmap,
                   norm=BoundaryNorm(bounds, cmap.N), aspect="equal", interpolation="nearest")
    cb = fig.colorbar(im, ax=ax, shrink=0.75, ticks=bounds)
    cb.set_label("payload at the reducer rated torques, kg (best configuration)")
    ax.axhline(0, color="#52514e", lw=0.8)
    ax.text(10, 15, "ОПУ face", fontsize=8, color="#52514e")
    ax.set_xlabel("flange: horizontal distance from the J1 axis, mm")
    ax.set_ylabel("flange height above the ОПУ face, mm")
    ax.set_title(f"RTC-7: static payload zones (tool interface {IFACE['mass']:g} kg included)\n"
                 f"green = {payload:g} kg and more", fontsize=10)
    ax.grid(color="white", lw=0.3, alpha=0.5)
    fig.tight_layout()
    fig.savefig(png, dpi=120)
    return A


def worst(lay, bl, n_rand=4000, seed=1):
    n = len(lay["axes"])
    rng = np.random.default_rng(seed)
    best = np.zeros(n)
    bestq = [np.zeros(n) for _ in range(n)]
    cand = [rng.uniform(-math.pi, math.pi, n) for _ in range(n_rand)]
    # classic candidates: arm stretched horizontally in both directions, roll joints at 0/90
    for q2 in (math.pi / 2, -math.pi / 2):
        for r in (0, math.pi / 2, -math.pi / 2):
            cand.append(np.array([0, q2, r, 0, r, 0, r]))
    for q in cand:
        q[0] = 0.0
        t = torques(lay, bl, q)
        for i in range(n):
            if t[i] > best[i]:
                best[i], bestq[i] = t[i], q.copy()
    # local refinement per joint
    for i in range(n):
        q = bestq[i].copy()
        step = math.radians(20)
        while step > math.radians(0.5):
            improved = False
            for k in range(1, n):
                for s in (step, -step):
                    q2 = q.copy()
                    q2[k] += s
                    t = torques(lay, bl, q2)[i]
                    if t > best[i] + 1e-9:
                        best[i], q, improved = t, q2, True
            if not improved:
                step /= 2
        bestq[i] = q
    return best, bestq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("layout")
    ap.add_argument("--payload", type=float, default=5.0, help="kg at the flange, for the report")
    ap.add_argument("--tool", type=float, default=100.0, help="payload COM beyond the flange, mm")
    ap.add_argument("--eta", type=float, default=0.8)
    ap.add_argument("--interface", type=float, default=4.0, help="tool-change interface on J7, kg (always on)")
    ap.add_argument("--md")
    ap.add_argument("--png")
    ap.add_argument("--map", help="payload zone map PNG (static, rated torques)")
    a = ap.parse_args()
    lay = rs.read_layout(a.layout)
    IFACE["mass"] = a.interface
    n = len(lay["axes"])
    b0, notes = bodies(lay, 0.0, a.tool)
    b1, _ = bodies(lay, 1.0, a.tool)
    self_t, self_q = worst(lay, b0)
    # torque per kg of payload in the self-weight worst pose, and its own worst
    per_kg = np.array([torques(lay, b1, self_q[i])[i] - self_t[i] for i in range(n)])
    bP, _ = bodies(lay, a.payload, a.tool)
    tot_t, tot_q = worst(lay, bP, n_rand=2000, seed=2)

    env_names = [x["joint"] for x in lay["axes"]]
    rated, ss, motT, motn, mname = [], [], [], [], []
    for nm in env_names:
        j = je.read_joint(os.path.join(ROOT, "joints", nm.rstrip("m"), nm.rstrip("m") + ".txt"))
        rd = card_data(os.path.join(ROOT, j["use"]["reducer"]))
        md = card_data(os.path.join(ROOT, j["use"]["motor"]))
        rated.append(float(rd["T_rated"]))
        ss.append(float(rd["T_startstop"]))
        motT.append(float(md["T_rated"]))      # an actuator card (AK80-9) gives it already after its own gear
        motn.append(float(md["n_rated"]))
        mname.append(rd.get("ratios", ""))

    L = [f"# RTC-7: static gravity torques (`python tools/robot_statics.py {a.layout}`)", "",
         "Gravity only (no accelerations), worst pose over all angles of J2..J7 (no joint limits yet).",
         f"Tool-change interface {a.interface:g} kg always on the flange (COM {IFACE['com']:g} mm out); payload COM {a.tool:g} mm beyond the flange. Reducer efficiency eta = {a.eta}.", "",
         "## Mass model", "", "| Body | Mass, kg | Moves with |", "|---|---|---|"]
    for m, p, k, nm in b0:
        L.append(f"| {nm} | {m:.2f} | link {k} |")
    L += [f"| **total moving above J2** | **{sum(m for m, p, k, _ in b0 if k >= 1):.1f}** | |", ""]
    L += [f"- {x}" for x in notes]
    L += ["- links are ASSUMED (aluminium tubes and fittings, `LINKS` in the script) until they are designed", "",
          "## Worst static torques", "",
          f"| Joint | Drive | Self-weight, N·m | Per 1 kg payload, N·m/kg | With {a.payload:g} kg, N·m "
          "| Reducer rated / start-stop, N·m | Payload at rated torque, kg | Ratio needed (motor rated) |",
          "|---|---|---|---|---|---|---|---|"]
    pay_lim = []
    for i in range(n):
        pl = (rated[i] - self_t[i]) / per_kg[i] if per_kg[i] > 1e-6 else float("inf")
        if i:
            pay_lim.append((pl, i))
        need = tot_t[i] / (motT[i] * a.eta)
        ratios = [int(r) for r in mname[i].split("/") if r]
        pick = next((r for r in ratios if r >= need), None)
        ptxt = "-" if i == 0 else (f"{pl:.1f}" if pl != float("inf") else "-")
        rtxt = "-" if i == 0 or tot_t[i] < 1 else f"{need:.0f} -> {pick if pick else 'none'}" + (
            f" (n_out {motn[i] / pick:.0f} rpm)" if pick else "")
        L.append(f"| J{i + 1} | {env_names[i]} | {self_t[i]:.0f} | {per_kg[i]:.1f} | {tot_t[i]:.0f} | "
                 f"{rated[i]:.0f} / {ss[i]:.0f} | {ptxt} | {rtxt} |")
    lim, li = min(pay_lim)
    L += ["", f"Static payload limit at the reducer rated torque: **{lim:.1f} kg**, set by J{li + 1}.",
          "J1 axis is vertical: no gravity torque, it carries only the inertia (and the ОПУ takes the tilting moment).",
          "Dynamic loads (accelerations) come on top; start-stop torque is the catalog limit for them.", "",
          "Worst poses (deg, J1..J7):", ""]
    for i in range(1, n):
        L.append(f"- J{i + 1}: " + ", ".join(f"{math.degrees(v):.0f}" for v in self_q[i]))
    if a.map:
        A = capacity_map(lay, b0, b1, rated, os.path.join(ROOT, a.map), a.payload)
        ok = A[A[:, 2] >= a.payload]
        L += ["", f"## Payload zones (static, rated torques; poses in the arm plane, best configuration)", "",
              f"- reach with {a.payload:g} kg: flange up to {ok[:, 0].max():.0f} mm from the J1 axis"
              if len(ok) else f"- {a.payload:g} kg: nowhere at the rated torques",
              f"- full reach (any payload >= 0): {A[A[:, 2] >= 0][:, 0].max():.0f} mm", f"- map: `{a.map}`"]
    rep = "\n".join(L) + "\n"
    print(rep)
    if a.md:
        open(os.path.join(ROOT, a.md), "w", encoding="utf-8").write(rep)
    if a.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 4.8))
        idx = np.arange(1, n)
        names = [f"J{i + 1}  {env_names[i]}" for i in idx]
        r = np.array(rated)
        sw = 100 * self_t[idx] / r[idx]
        pl = 100 * (tot_t[idx] - self_t[idx]) / r[idx]
        y = np.arange(len(idx))
        ax.barh(y, sw, color="#2a78d6", height=0.55, label="self-weight")
        ax.barh(y, pl, left=sw + 0.6, color="#eb6834", height=0.55, label=f"payload {a.payload:g} kg")
        for k, i in enumerate(idx):
            ax.text(sw[k] + pl[k] + 2, k, f"{tot_t[i]:.0f} of {rated[i]:.0f} N·m", va="center",
                    fontsize=8.5, color="#0b0b0b")
            ax.plot([100 * ss[i] / rated[i]] * 2, [k - 0.33, k + 0.33], color="#52514e", lw=1.2, ls="--")
        ax.axvline(100, color="#0b0b0b", lw=1.2)
        ax.text(101, len(idx) - 0.55, "reducer rated", fontsize=8, color="#0b0b0b", va="center")
        ax.plot([], [], color="#52514e", lw=1.2, ls="--", label="reducer start-stop")
        ax.set_yticks(y, names, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlim(0, 270)
        ax.set_xlabel("worst static torque, % of the reducer rated torque")
        ax.grid(axis="x", color="0.92", lw=0.6)
        for sp_ in ("top", "right"):
            ax.spines[sp_].set_visible(False)
        ax.legend(frameon=False, fontsize=8, loc="lower right")
        ax.set_title("RTC-7: gravity torque in the worst pose, share of the reducer rating", fontsize=11)
        fig.tight_layout()
        fig.savefig(os.path.join(ROOT, a.png), dpi=120)


if __name__ == "__main__":
    main()
