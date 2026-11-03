#!/usr/bin/env python3
"""TCP deflection of the user's arm with RIGID joints (sensors on every output, user 2026-10-26): each link in CalculiX
(tools/fea_link_quick.py, self-weight + the weight of everything after it on its distal seat, fixed on its proximal
seat), the ОПУ tilt (K = 5.4e6 N*m/rad), composed at the TCP.   python tools/tcp_stiffness.py [--q 0,90,0,0,0,0,0]
Pose default: the arm stretched horizontally (J2 90). Payload 8 kg 200 mm beyond the TCP + SZU (as user_loads).
Out: fea/stiffness/summary.md."""
import argparse, math, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K_OPU = 5.4e6                      # N*m/rad, RU178G (THK RB15025 analogue)
#        group  card                                  E       rho   h    fixed selector / load selector / load centre (card)
LINKS = [("L1", "links-user/LINK-1U/LINK-1U.txt", 210000, 7850, 5.0,
          "x0:-135.5..-134.5|rx:0,-85,0,57..80;x0:-135..-123|rx:0,-85,0,57..58",
          "z0:-0.5..0.5|rz:0,0,0,95..111;z0:0..10|rz:0,0,0,94.5..95.5", (0, 0, 0)),
         ("L2", "links-user/LINK-2B/LINK-2B.txt", 210000, 7850, 5.0,
          "z0:13.5..14.5|rz:0,0,0,0..80.5", "y0:0.5..1.5|ry:0,150,0,107..118.5", (0, 1, 150)),
         ("L3", "links-user/LINK-3U/LINK-3U.txt", 71000, 2700, 8.0,
          "z0:383.5..384.5|rz:135,0,0,40..86", "x0:66.5..67.5|rx:0,1557,0,84..110", (67, 0, 1557)),
         ("L4", "links-user/LINK-4U/LINK-4U.txt", 210000, 7850, 5.0,
          "x0:-0.5..3.5|rx:88,75,0,39.5..79.5", "y0:-0.5..0.5|ry:85,75,0,69.5..86", (85, 0, 75)),
         ("L5", "links-user/LINK-5U/LINK-5U.txt", 71000, 2700, 6.0,
          "z0:1643.5..1644.5|rz:-144,0,0,26..56", "x0:-94.5..-93.5|rx:0,2527,0,47..68", (-94, 0, 2527))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", default="0,90,0,0,0,0,0")
    ap.add_argument("--payload", type=float, default=8.0)
    ap.add_argument("--pay-off", type=float, default=200.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "fea", "stiffness"))
    a = ap.parse_args()
    argv = sys.argv; sys.argv = [argv[0]]
    import cart_reach as cr, gen_user_full as gf, gen_user_l123 as g
    sys.argv = argv
    q = np.radians([float(v) for v in a.q.split(",")])
    arm = cr.Arm(geometry=True)
    _, cum = arm.fk(q)
    G = np.array([-9.81, 0, 0])                     # m/s^2, arm frame (X up)
    bodies = [(gr, cr.MASS[gr], (cum[cr.NMOV[gr]] @ np.r_[arm.com[gr], 1])[:3]) for gr in cr.MASS]
    bodies.append(("PAY", a.payload, (cum[7] @ np.r_[arm.tcp0 + a.pay_off * arm.app0, 1])[:3]))
    tcp = (cum[7] @ np.r_[arm.tcp0, 1])[:3]
    order = cr.ORDER + ["PAY"]
    place = {"L1": g.frame([171, 16.5826773713467, 83.3667488342793], [1, 0, 0], [0, 0.195090322015843, 0.980785280403287]),
             "L2": g.L2}
    for n in ("L3", "L4", "L5"):
        place[n] = gf.place(n)
    rows = []; total = np.zeros(3)
    os.makedirs(a.out, exist_ok=True)
    for grp, card, E, rho, h, fsel, lsel, cc in LINKS:
        W = cum[cr.NMOV[grp]] @ place[grp]; R = W[:3, :3]
        c = (W @ np.r_[cc, 1])[:3]
        down = [b for b in bodies if order.index(b[0]) > order.index(grp)]
        F = sum(m * G for _, m, _ in down)                                   # N
        M = sum(np.cross(p - c, m * G) for _, m, p in down)                  # N*mm
        Fc, Mc = R.T @ F, R.T @ M; gc = R.T @ np.array([-1.0, 0, 0])
        case = "G:" + ",".join(f"{v:.3f}" for v in (*Fc, *Mc))
        cmd = [sys.executable, os.path.join(ROOT, "tools", "fea_link_quick.py"), os.path.join(ROOT, card), "--out",
               os.path.join(a.out, grp), "--h", str(h), "--E", str(E), "--name", grp, "--fixed", fsel, "--load", lsel,
               "--center=" + ",".join(str(v) for v in cc), "--case", case, "--grav=" + ",".join(f"{v:.6f}" for v in gc),
               "--rho", str(rho)]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        line = [l for l in r.stdout.splitlines() if l.startswith("G ")]
        if not line:
            print(grp, "FAILED", r.stdout[-1500:], r.stderr[-1500:]); return
        nums = [float(v) for v in re.findall(r"-?\d+\.\d+", line[0])]
        u, th = np.array(nums[0:3]), np.array(nums[3:6]) * 1e-3
        uw, thw = R @ u, R @ th
        d = uw + np.cross(thw, tcp - c)
        total += d
        mass = sum(m for _, m, _ in down)
        print(f"{grp}: load {mass:.1f} kg, |M| {np.linalg.norm(M)/1e3:.0f} N*m, seat rot {np.linalg.norm(th)*1e3:.3f} mrad, "
              f"TCP {d.round(2)} mm  vM {nums[6]:.0f}/{nums[7]:.0f} MPa", flush=True)
        rows.append((grp, card, mass, np.linalg.norm(M) / 1e3, np.linalg.norm(th) * 1e3, np.linalg.norm(u), d, nums[6], nums[7]))
    # ОПУ tilt: everything on the inner ring
    on = [b for b in bodies if order.index(b[0]) >= order.index("L1")]
    Mo = sum(np.cross(p, m * G) for _, m, p in on) / 1e3                        # N*m about the ring centre
    tho = Mo / K_OPU
    do = np.cross(tho, tcp)
    total += do
    print(f"ОПУ: tilt {np.linalg.norm(Mo):.0f} N*m, {np.linalg.norm(tho)*1e3:.3f} mrad, TCP {do.round(2)} mm")
    print(f"TOTAL TCP {total.round(2)} mm, |d| {np.linalg.norm(total):.2f}, vertical {total[0]:.2f} mm; reach {np.hypot(*tcp[1:]):.0f} mm")
    L = [f"# TCP deflection, rigid joints - `python tools/tcp_stiffness.py --q {a.q}`", "",
         f"Pose q = {a.q} deg (J2 90 = the arm stretched horizontally), TCP reach {np.hypot(*tcp[1:]):.0f} mm, height {tcp[0]:.0f} mm.",
         f"Payload {a.payload:g} kg {a.pay_off:g} mm beyond the TCP + SZU 4 kg; link self-weight included (CalculiX GRAV).",
         "Each link: fixed on its proximal seat (rigid joint), the weight of everything after it on its distal seat (rigid body).", "",
         "| Link | card | load, kg | moment at the seat, N·m | seat rotation, mrad | vM max / far, MPa | TCP, mm (vertical) | TCP, mm (total) |",
         "|---|---|---|---|---|---|---|---|"]
    for grp, card, mass, Mm, th, u, d, v1, v2 in rows:
        L.append(f"| {grp} | `{card}` | {mass:.1f} | {Mm:.0f} | {th:.3f} | {v1:.0f} / {v2:.0f} | {d[0]:.2f} | {np.linalg.norm(d):.2f} |")
    L.append(f"| ОПУ | K {K_OPU:.1e} N·m/rad | - | {np.linalg.norm(Mo):.0f} | {np.linalg.norm(tho)*1e3:.3f} | - | {do[0]:.2f} | {np.linalg.norm(do):.2f} |")
    L += ["", f"**TCP: {np.linalg.norm(total):.2f} mm total, {total[0]:.2f} mm vertical** (link 6, Юла, plate, joints not included: rigid / ~0.05 mm)."]
    open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")



# ---- compliance of every link (linear: 6 unit loads at the seat centre + self-weight along the 3 card axes) ----------
UNIT = ["Fx:1000,0,0,0,0,0,0,0,0", "Fy:0,1000,0,0,0,0,0,0,0", "Fz:0,0,1000,0,0,0,0,0,0",
        "Mx:0,0,0,1e6,0,0,0,0,0", "My:0,0,0,0,1e6,0,0,0,0", "Mz:0,0,0,0,0,1e6,0,0,0",
        "gx:0,0,0,0,0,0,1,0,0", "gy:0,0,0,0,0,0,0,1,0", "gz:0,0,0,0,0,0,0,0,1"]


def compliance(out, links=None):
    """{grp: (C 6x6 [u mm; th rad] per [F N; M N*mm], Gw 6x3 per unit gravity direction)} -> out/compliance.json"""
    import json
    res = {}
    for grp, card, E, rho, h, fsel, lsel, cc in LINKS:
        if links and grp not in links:
            continue
        cmd = [sys.executable, os.path.join(ROOT, "tools", "fea_link_quick.py"), os.path.join(ROOT, card), "--out",
               os.path.join(out, grp), "--h", str(h), "--E", str(E), "--name", grp, "--fixed", fsel, "--load", lsel,
               "--center=" + ",".join(str(v) for v in cc), "--rho", str(rho)] + sum((["--case", c] for c in UNIT), [])
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        vals = {}
        for l in r.stdout.splitlines():
            t = l.split()
            if t and t[0] in [c.split(":")[0] for c in UNIT]:
                nums = [float(v) for v in re.findall(r"-?\d+\.\d+", l)]
                vals[t[0]] = np.r_[nums[0:3], np.array(nums[3:6]) * 1e-3]
        if len(vals) != 9:
            print(grp, "FAILED", r.stdout[-1500:], r.stderr[-800:]); continue
        C = np.c_[[vals[k] / 1000.0 for k in ("Fx", "Fy", "Fz")] + [vals[k] / 1e6 for k in ("Mx", "My", "Mz")]].T
        Gw = np.c_[[vals[k] for k in ("gx", "gy", "gz")]].T
        res[grp] = (C.tolist(), Gw.tolist())
        print(grp, "compliance ok", flush=True)
    old = json.load(open(os.path.join(out, "compliance.json"))) if os.path.isfile(os.path.join(out, "compliance.json")) else {}
    old.update(res)
    json.dump(old, open(os.path.join(out, "compliance.json"), "w"), indent=1)
    return old


class Arm:
    """fast TCP deflection for any pose from the link compliances (compliance.json)"""
    def __init__(self, out, payload=8.0, pay_off=200.0):
        import json
        argv = sys.argv; sys.argv = [argv[0]]
        import cart_reach as cr, gen_user_full as gf, gen_user_l123 as g
        sys.argv = argv
        self.cr = cr; self.arm = cr.Arm(geometry=True); self.payload = payload; self.pay_off = pay_off
        self.comp = {k: (np.array(v[0]), np.array(v[1])) for k, v in json.load(open(os.path.join(out, "compliance.json"))).items()}
        self.place = {"L1": g.frame([171, 16.5826773713467, 83.3667488342793], [1, 0, 0], [0, 0.195090322015843, 0.980785280403287]),
                      "L2": g.L2}
        for n in ("L3", "L4", "L5"):
            self.place[n] = gf.place(n)

    def tcp(self, q_deg):
        _, cum = self.arm.fk(np.radians(q_deg))
        return (cum[7] @ np.r_[self.arm.tcp0, 1])[:3], cum[7][:3, :3] @ self.arm.app0

    def deflection(self, q_deg, parts=False, pay_off=None):
        cr, arm = self.cr, self.arm
        po = self.pay_off if pay_off is None else pay_off
        _, cum = arm.fk(np.radians(q_deg))
        G = np.array([-9.81, 0, 0])
        bodies = [(gr, cr.MASS[gr], (cum[cr.NMOV[gr]] @ np.r_[arm.com[gr], 1])[:3]) for gr in cr.MASS]
        bodies.append(("PAY", self.payload, (cum[7] @ np.r_[arm.tcp0 + po * arm.app0, 1])[:3]))
        tcp = (cum[7] @ np.r_[arm.tcp0, 1])[:3]
        order = cr.ORDER + ["PAY"]; out = {}; tot = np.zeros(3)
        for grp, card, E, rho, h, fsel, lsel, cc in LINKS:
            C, Gw = self.comp[grp]
            W = cum[cr.NMOV[grp]] @ self.place[grp]; R = W[:3, :3]; c = (W @ np.r_[cc, 1])[:3]
            down = [b for b in bodies if order.index(b[0]) > order.index(grp)]
            F = sum(m * G for _, m, _ in down); M = sum(np.cross(p - c, m * G) for _, m, p in down)
            x = C @ np.r_[R.T @ F, R.T @ M] + Gw @ (R.T @ np.array([-1.0, 0, 0]))
            d = R @ x[:3] + np.cross(R @ x[3:], tcp - c); out[grp] = d; tot = tot + d
        on = [b for b in bodies if order.index(b[0]) >= order.index("L1")]
        Mo = sum(np.cross(p, m * G) for _, m, p in on) / 1e3
        do = np.cross(Mo / K_OPU, tcp); out["OPU"] = do; tot = tot + do
        return (tot, out) if parts else tot


if __name__ == "__main__":
    if "--compliance" in sys.argv:
        sys.argv.remove("--compliance"); compliance(os.path.join(ROOT, "fea", "stiffness"))
    else:
        main()
