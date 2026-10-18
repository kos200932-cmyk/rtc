#!/usr/bin/env python3
"""Compact layout of the RTC-7 arm from the scheme topology, the real joint envelopes and the cable path.

    python tools/robot_layout.py [--l3 1330] [--l5 1150] [--gap 10] [--plate 10]
                                 [--k 4] [--clear 4] [--rb34 R --rb45 R --rb56 R --rb67 R]
                                 [--out robot/RTC-7-layout.txt]

Topology (user's scheme, 2026-10-18 v2): J1 = ШМ-150м (ШМ-150 + ОПУ RU178G; the outer ring stands on
the horizontal base plane, the whole arm on the inner ring), J2 pitch (axis X, motor -X), J3 roll
(motor down), J4 pitch (motor +X), J5 roll, J6 pitch (motor -X), J7 roll, tool flange up.
Given: the link lengths J2->J4 (l3) and J4->J6 (l5) along Z.

Cable: enters J3 and runs through the central bores J3 -> J4 -> J5 -> J6 -> J7. Between two joints
it turns 90 deg with the bend radius Rb (centre line) outside the joints:
    Rb = k * d,  d = min(cable, smaller bore of the two joints - clear)   (user: cable 20, k = 2)
or given directly with --rbXY. The cable enters a joint through its rear (motor) end and leaves
through the output end.

Rules (everything not given is minimised; gap g, link plate t):
  J2   output face on the J1 axis (x = 0) as drawn; axis height = max(J2 radius + g over the fixed
       ОПУ outer ring, t + g + R3 so the upper arm can swing to horizontal over link 1).
  J3   column right behind the link-2 plate: x3 = t + R3; its lowest point (rear cover with the
       sensor allowance) 200 mm above the ОПУ face - the cable loop from the base plane is formed there.
  J4   cable J3 -> J4 rear: x3 >= J4 rear end + Rb34  -> J4 output face x = x3 - Rb34 - L4.
  J5   cable J4 output -> J5 rear: x5 = J4 face - t - Rb45; J5 rear end >= z4 + Rb45 (raised a bit);
       J5 sits lower than the J4 housing radius, so its column also keeps g from the fixed J4 housing
       (which starts a few mm behind the output face).
  J6   cable J5 output -> J6 rear: J6 rear end >= x5 + Rb56 -> J6 face = x5 + Rb56 + L6;
       J5 output face <= z6 - t - Rb56 (checked).
  J7   cable J6 output -> J7 rear: x7 = J6 face + t + Rb67; J7 rear end >= z6 + Rb67; the J7 column
       keeps g from the fixed J6 housing as for J5.
  checks: the roll columns on both sides of a pitch joint are >= R + R' + t + g apart (the links
  can fold past each other); the J3 output face is below z4 - t - Rb34.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_envelope as je  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPU_B = 28.0          # RU178G width (ASSUMED as IKO RU178), outer ring on the base plane


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--l3", type=float, default=1330.0, help="J2 -> J4 along the arm, mm")
    ap.add_argument("--l5", type=float, default=1150.0, help="J4 -> J6 along the arm, mm")
    ap.add_argument("--gap", type=float, default=10.0)
    ap.add_argument("--plate", type=float, default=10.0)
    ap.add_argument("--k", type=float, default=2.0, help="min bend radius / cable diameter (user: 2)")
    ap.add_argument("--cable", type=float, default=20.0, help="cable bundle diameter J3->J4 (user: 20); "
                    "further on the same or thinner, limited by the bores")
    ap.add_argument("--clear", type=float, default=4.0, help="cable diameter <= bore - clear")
    ap.add_argument("--j3-rear", type=float, default=200.0,
                    help="lowest point of J3 (rear cover incl.) above the ОПУ face - room for the cable loop (user: 200)")
    for s in ("34", "45", "56", "67"):
        ap.add_argument(f"--rb{s}", type=float, help=f"bend radius J{s[0]} -> J{s[1]}, mm")
    ap.add_argument("--out", default="robot/RTC-7-layout.txt")
    a = ap.parse_args()
    g, t = a.gap, a.plate
    env = je.all_joints()
    E1, E2, E3, E4, E5, E6, E7 = (env[n] for n in ("SHM-150", "SHM-1000", "SHM-500", "SHM-500",
                                                    "SHM-150", "SHM-150", "SHM-60"))
    rb, dc = {}, {}
    for s, ea, eb in (("34", E3, E4), ("45", E4, E5), ("56", E5, E6), ("67", E6, E7)):
        dc[s] = min(a.cable, min(ea["bore"], eb["bore"]) - a.clear)
        rb[s] = getattr(a, f"rb{s}") or a.k * dc[s]

    # ---- J1: ШМ-150 under the ОПУ; its housing top clears the inner ring (z -B..0) by g
    z1_face = -OPU_B - g + (E1["x_out"] - max(x1 for x0, x1, r, n in E1["fixed"]))
    # ---- J2
    xf2 = 0.0
    z2 = max(E2["R"] + g, t + g + E3["R"])
    # ---- J3
    x3 = xf2 + t + E3["R"]
    z3_rear = a.j3_rear
    z3_face = z3_rear + E3["L"]
    z4 = z2 + a.l3
    # ---- J4 (output -X): rear end at x3 - Rb34
    xf4 = x3 - rb["34"] - E4["L"]
    # ---- J5
    front = lambda e: e["x_out"] - max(x1 for x0, x1, r, n in e["fixed"])   # output face -> fixed housing
    # cable bend, and the J5 body (low, beside J4) must clear the fixed J4 housing behind the output flange
    x5 = min(xf4 - t - rb["45"], xf4 + front(E4) - g - E5["R"])
    z5_rear = z4 + rb["45"]
    z5_face = z5_rear + E5["L"]
    z6 = z4 + a.l5
    # ---- J6 (output +X): rear end at x5 + Rb56
    xf6 = x5 + rb["56"] + E6["L"]
    # ---- J7
    x7 = max(xf6 + t + rb["67"], xf6 - front(E6) + g + E7["R"])
    z7_rear = z6 + rb["67"]
    z7_face = z7_rear + E7["L"]

    checks = [("J3 output face below the J3->J4 cable bend", z3_face, z4 - t - rb["34"]),
              ("J5 output face below the J5->J6 cable bend", z5_face, z6 - t - rb["56"]),
              ("links fold past each other at J4 (columns J3/J5)", E3["R"] + E5["R"] + t + g, x3 - x5),
              ("links fold past each other at J6 (columns J5/J7)", E5["R"] + E7["R"] + t + g, x7 - x5),
              ("J2 body over the ОПУ outer ring", g, z2 - E2["R"])]
    bad = [c for c in checks if c[1] > c[2] + 1e-9]
    for name, v, lim in checks:
        print(f"{'OK ' if v <= lim + 1e-9 else 'BAD'} {name}: {v:.1f} <= {lim:.1f}")

    L = []
    w = L.append
    rbtxt = ", ".join(f"J{s[0]}->J{s[1]} {rb[s]:.0f} (cable D{dc[s]:.0f})" for s in rb)
    w("# Kinematic layout of the arm - GENERATED by tools/robot_layout.py (do not edit by hand,")
    w(f"# change the rules / arguments there):  --l3 {a.l3:g} --l5 {a.l5:g} --gap {g:g} --plate {t:g} --k {a.k:g}")
    w("# Topology from the user's scheme (2026-10-18, v2); J1 = ШМ-150м: ОПУ outer ring on the base plane,")
    w("# the arm on the inner ring. Given: J2->J4 = l3, J4->J6 = l5; the rest minimised from the joint")
    w("# envelopes and the cable path through the central bores J3..J7 (90 deg turns between joints).")
    w(f"# Cable bend radii (centre line): {rbtxt}")
    w("ROBOT RTC-7")
    w("UNITS mm deg")
    w("# World frame = the X/Y frame of the scheme: origin on the J1 axis at the top face of the ОПУ,")
    w("# +Z up along J1, +X to the right (toward the J3 column), +Y = Z x X (into the scheme).")
    w("# AXIS name joint  point on the axis (x y z)  direction  motor/output side  face= output face centre")
    rows = [
        ("J1", "SHM-150m", (0, 0, 0), (0, 0, 1), "-Z", "+Z", (0, 0, z1_face), "base turn: ШМ-150 under the ОПУ RU178G, output -> inner ring (link 1)"),
        ("J2", "SHM-1000", (0, 0, z2), (1, 0, 0), "-X", "+X", (xf2, 0, z2), "shoulder; output face on the J1 axis"),
        ("J3", "SHM-500", (x3, 0, z2), (0, 0, 1), "-Z", "+Z", (x3, 0, z3_face), "upper-arm roll; cables enter here from the loop below (bottom 200 above the ОПУ)"),
        ("J4", "SHM-500", (x3, 0, z4), (1, 0, 0), "+X", "-X", (xf4, 0, z4), f"elbow; {a.l3:g} above J2; rear end Rb34 from the J3 axis"),
        ("J5", "SHM-150", (x5, 0, z4), (0, 0, 1), "-Z", "+Z", (x5, 0, z5_face), "forearm roll; rear end Rb45 above J4"),
        ("J6", "SHM-150", (x5, 0, z6), (1, 0, 0), "-X", "+X", (xf6, 0, z6), f"wrist; {a.l5:g} above J4; rear end Rb56 from the J5 axis"),
        ("J7", "SHM-60", (x7, 0, z6), (0, 0, 1), "-Z", "+Z", (x7, 0, z7_face), "flange roll; rear end Rb67 above J6"),
    ]
    f3 = lambda v: " ".join(f"{c:g}" if float(c).is_integer() else f"{c:.1f}" for c in v)
    for n, j, p, d, m, o, face, c in rows:
        fs = f"face={','.join(f'{v:.1f}' for v in face)}"
        w(f"AXIS  {n}  {j:<9} {f3(p):<18} {f3(d):<7} motor={m} output={o} {fs:<28} # {c}")
    w("# Cable path (centre line through the bores, zero pose) for drawing and checks:")
    path = [(x3, z3_rear - 30), (x3, z4 - rb["34"]), ("arc", x3 - rb["34"], z4 - rb["34"], rb["34"], 0, 90),
            (x3 - rb["34"], z4), (x5 + rb["45"], z4), ("arc", x5 + rb["45"], z4 + rb["45"], rb["45"], 270, 180),
            (x5, z4 + rb["45"]), (x5, z6 - rb["56"]), ("arc", x5 + rb["56"], z6 - rb["56"], rb["56"], 180, 90),
            (x5 + rb["56"], z6), (x7 - rb["67"], z6), ("arc", x7 - rb["67"], z6 + rb["67"], rb["67"], 270, 360),
            (x7, z6 + rb["67"]), (x7, z7_face + 20)]
    for p in path:
        if p[0] == "arc":
            w(f"CABLE arc {p[1]:.1f} {p[2]:.1f} {p[3]:.1f} {p[4]:g} {p[5]:g}   # centre x z, radius, from..to deg (0 = +X, 90 = +Z)")
        else:
            w(f"CABLE pt  {p[0]:.1f} {p[1]:.1f}")
    w("# Tool flange = output face of ШМ-60 (the tool is not on the scheme).")
    w(f"FLANGE {f3((x7, 0, z7_face))}   0 0 1")
    w("END")
    out = os.path.join(ROOT, a.out)
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\nlateral: J1->J3 {x3:.1f}, J3->J5 {x3 - x5:.1f}, J5->J7 {x7 - x5:.1f}; ОПУ->J2 {z2:.1f}; "
          f"J4->J5 rear {rb['45']:.1f}; J6->J7 rear {rb['67']:.1f}; J6 -> flange {z7_face - z6:.1f}; "
          f"J1 output face z {z1_face:.1f}")
    if bad:
        sys.exit("layout check FAILED")


if __name__ == "__main__":
    main()
