#!/usr/bin/env python3
"""Generate the spec of a link (welded / plate construction) from the layout and the joint ports.

    python tools/link_gen.py 1 [--layout robot/RTC-7-layout.txt]     -> links/LINK-1/LINK-1.txt

Link 1 (J1 -> J2), welded aluminium (all sizes are parameters below, mm):
  * 01_Weldment - base flange on the ОПУ inner ring (D <= ds 161, central hole for the J1 adapter
    screws), deck under the J2 flange (keeps the gap over the fixed outer ring), J2 mounting plate
    (bore = J2 pilot, tapped holes on the J2 flange circle), two side ribs outside the J2 flange;
    12 screws from the top through the flange and the inner ring into the J1 adapter (access holes in
    the deck above them);
  * 02_J1Adapter - under the inner ring: recess on the ШМ-150 (KB32) output spigot + its screws,
    tapped holes for the 12 ring screws.
The output is a spec for tools/link_build.py (STEP, checks) and macros/BuildFromSpec.bas (SolidWorks).
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_envelope as je  # noqa: E402
import robot_scheme as rs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ОПУ RU178G (components/ISKRA/RU178G): inner ring bore 115, OD 177, B 28, 12 x D9 on 139 at 0 deg; ds 161
OPU = {"B": 28.0, "d": 115.0, "pcd": 139.0, "n": 12, "hole": 9.0, "ang": 0.0, "ds": 161.0}
P1 = {
    "plate_half": 125.0, "plate_t": 20.0, "boss_h": 5.0, "boss_D": 160.0, "bore": 112.0,
    # base plate: one machined plate over the whole ОПУ (D240): boss D160 (<= ds 161) x 5 on the inner ring,
    # the rest of the plate 5 mm over the fixed outer ring
    "j2plate_t": 20.0, "j2plate_margin": 22.0,                     # J2 plate: half width = PCD/2 + margin
    "rib_t": 12.0, "rib_gap": 2.0,                                 # side ribs outside the J2 flange, full length
    "j2_range": 90.0, "gap": 10.0,                                 # J2 travel the ribs must let link 2 / J3 pass over
    "cbore_D": 16.0, "cbore_depth": 8.6,
    "corner_R": 20.0, "j2plate_R": 50.0,                          # rounded corners: base plate, J2 plate top                           # M8 heads (D14 x 8.6) + wrench access
    "adapter_t": 15.0, "adapter_recess": 8.0, "adapter_D": 155.0, "adapter_hole": 50.0,
}
KB32_OUT = {"fit": 112.0, "pcd": 100.0, "n": 16, "hole": 5.5, "ang": 101.25}
J2_BASE = {"pilot": 190.0, "pcd": 206.0, "n": 16, "size": "M8", "ang_joint": 90.0}
# DMRD-80E output (J2): D160h7 (joint x 132..143), end plate D159 to the face; 9 x M8 on D142 in 3 groups
# (69/81/99 deg + 120k), 6 x M10 on D110 (80/100 + 120k), 3 x Rc1/8 plugs on D142 at 111 + 120k (joint angles)
J2_OUT = {"fit": 160.0, "fit_len": 11.0, "m8": (142.0, (69.0, 81.0, 99.0)), "m10": (110.0, (80.0, 100.0)),
          "plug": (142.0, 111.0)}
# ШМ-500 base (J3): pilot D168h7 (13 long, motor side of the flange D190), 9 x D6.6 on D180 at 110 + 40k
J3_BASE = {"pilot": 168.0, "pilot_len": 13.0, "pcd": 180.0, "n": 9, "size": "M6", "ang_joint": 110.0,
           "flange_D": 190.0}
# DMRD-KB45 output (J3, J5 later ШМ-150...): D158h7 (joint x 86..99), 16 x M8 on D140 at 101.25 + 22.5k
KB45_OUT = {"fit": 158.0, "fit_len": 13.0, "pcd": 140.0, "n": 16, "hole": 9.0, "ang": 101.25, "bore": 65.0}
P3 = {
    "skirt_D": 186.0, "skirt_len": 10.0, "flange_t": 20.0, "flange_hole": 60.0,   # on the J3 output
    "tube_D": 120.0, "tube_t": 5.0,                                            # upper-arm tube (on the J3 axis)
    "plate_t": 20.0, "plate_half": 105.0, "plate_R": 40.0,                     # J4 mounting plate
    "box_half": 90.0, "box_t": 10.0, "box_R": 15.0,                            # head box round the J4 motor + cable bend
}
# ШМ-150 base (J5 on link 4): pilot D122h7 (0..7, motor side of the flange D142), 12 x D5.5 on D132 at 90 + 30k
J5_BASE = {"pilot": 122.0, "pcd": 132.0, "n": 12, "size": "M5", "ang_joint": 90.0, "flange_D": 142.0}
P4 = {"plate_t": 20.0, "disc_R": 90.0, "skirt_D": 186.0, "skirt_len": 10.0, "cable_hole": 60.0,
      "half": 80.0, "shelf_t": 20.0, "shelf_R": 40.0, "wall_t": 10.0}
# DMRD-KB32 output (J5, J6): D112h7 (joint x 56.5..65.5), 16 x M5 (smooth D5.5 at the face) on D100 at 101.25
KB32_OUT2 = {"fit": 112.0, "pcd": 100.0, "n": 16, "hole": 5.5, "ang": 101.25}
# ШМ-60 base (J7 on link 6): pilot D94h7 (1.5..6.5), flange D110, 12 x D4.5 on D102 at 90 + 30k
J7_BASE = {"pilot": 94.0, "pcd": 102.0, "n": 12, "size": "M4", "ang_joint": 90.0, "flange_D": 110.0}
P5 = {"skirt_D": 140.0, "skirt_len": 6.0, "flange_t": 15.0, "flange_D": 140.0, "flange_hole": 50.0,
      "tube_D": 80.0, "tube_t": 4.0, "plate_t": 20.0, "plate_half": 85.0, "plate_R": 30.0,
      "box_half": 70.0, "box_t": 8.0, "box_R": 12.0}
P6 = {"plate_t": 10.0, "disc_R": 70.0, "skirt_D": 140.0, "skirt_len": 6.0, "cable_hole": 50.0,
      "half": 65.0, "shelf_t": 15.0, "shelf_R": 30.0, "wall_t": 8.0}
P2 = {
    "plate_t": 20.0, "disc_R": 95.0,          # plate on the J2 output: round below the J2 axis (sweeps over link 1)
    "skirt_D": 186.0, "skirt_len": 13.0,      # centring skirt on the J2 output D160h7 (axial gap 4 to the housing)
    "half": 100.0,                            # half width (y) of link 2 - also used for the link-1 rib check
    "shelf_t": 20.0, "wall_t": 10.0,          # J3 shelf under the J3 flange, side walls
    "shelf_R": 40.0,                          # rounded outer corners of the shelf
}


def plane_angle(u_axis, a, plane):
    """Angle in a link plane of a hole that sits at joint angle a (0 = +Zj, 90 = +Yj).
    Joint frame in the arm (same rule as tools/robot_asm.py and the macro): X_j = u_axis (output
    direction), Z_j = world +X for a joint along Z, world +Z for a joint along X, Y_j = Z_j x X_j.
    plane: 'X' -> (u, v) = (y, z); 'Y' -> (x, z); 'Z' -> (x, y)."""
    import math
    ex = np.array(u_axis, float)
    ez = np.array([1.0, 0, 0]) if abs(ex[2]) > 0.5 else np.array([0, 0, 1.0])
    ey = np.cross(ez, ex)
    d = math.sin(math.radians(a)) * ey + math.cos(math.radians(a)) * ez
    iu, iv = {"X": (1, 2), "Y": (0, 2), "Z": (0, 1)}[plane]
    return (math.degrees(math.atan2(d[iv], d[iu])) + 360.0) % 360.0


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def sweep_min_z(z2, x3, r3, s_top, band, j2_range):
    """Lowest point of link 2 + J3 (a column |y| <= r3, 0..s_top above the J2 axis) inside the band
    band = (y0, y1) of |y| while J2 turns by +-j2_range deg."""
    best = 1e9
    s = np.linspace(0, s_top, 160)
    for th in np.radians(np.linspace(-j2_range, j2_range, 361)):
        for yr in np.linspace(-r3, r3, 49):
            yp = yr * np.cos(th) - s * np.sin(th)
            zp = z2 + yr * np.sin(th) + s * np.cos(th)
            m = (np.abs(yp) >= band[0]) & (np.abs(yp) <= band[1])
            if m.any():
                best = min(best, zp[m].min())
    return best


def link1(lay):
    ax = {a["name"]: a for a in lay["axes"]}
    env = je.all_joints()
    E2, E3 = env["SHM-1000"], env["SHM-500"]
    j1, j2, j3 = ax["J1"], ax["J2"], ax["J3"]
    z2 = j2["p"][2]
    xf2 = j2["face"][0]
    g = P1["gap"]
    x_base = xf2 + (E2["x_base"] - E2["x_out"])        # J2 base face (world x), J2 plate on its -X side
    x_pl0, x_pl1 = x_base - P1["j2plate_t"], x_base
    hw = J2_BASE["pcd"] / 2 + P1["j2plate_margin"]      # J2 plate half width
    R2 = E2["R"]
    H = P1["plate_half"]
    z_b0, z_b1 = P1["boss_h"], P1["boss_h"] + P1["plate_t"]   # base plate z (boss below it, 0..boss_h)
    assert H >= 120, "the base plate must cover the ОПУ (D240)"
    assert abs(z2 - (z_b1 + R2 + 1)) < 0.5, f"layout J2 axis {z2} != plate top {z_b1} + R2 + 1: run robot_layout.py --deck {z_b1}"
    y_r0 = R2 + P1["rib_gap"]
    y_r1 = min(y_r0 + P1["rib_t"], H)
    z_j2top = z2 + hw
    # ribs run over the whole plate; where link 2 / J3 pass over them (x >= J2 output face - g) they are low:
    s_top = j3["face"][2] - z2                          # J3 output face above the J2 axis
    zmin = sweep_min_z(z2, j3["p"][0], max(E3["R"], P2["half"]), s_top, (y_r0 - g, y_r1 + g), P1["j2_range"])
    z_strip = min(zmin - g, z_j2top)
    x_sw = xf2 - g                                      # link-2 sweep zone starts here
    a_j2 = plane_angle((1, 0, 0), J2_BASE["ang_joint"], "X")    # J2 joint angle -> plane angle in (y, z)
    z_ad1 = -OPU["B"]
    z_ad0 = z_ad1 - P1["adapter_t"]
    z_face1 = z_ad0 + P1["adapter_recess"]
    assert abs(z_face1 - j1["face"][2]) < 0.05, f"J1 face {j1['face'][2]} vs adapter recess floor {z_face1}"
    assert P1["boss_D"] <= OPU["ds"] and P1["adapter_D"] <= OPU["ds"]
    Rp, rc = P1["corner_R"], P1["j2plate_R"]
    z_rt = z_j2top - rc - 5                         # rib top: below the rounded corner of the J2 plate
    # ribs: plain gussets, no rounding (user, 2026-10-19)
    rib = [(x_pl0, z_b1, 0), (x_pl0, z_rt, 0),
           (x_sw, max(z_strip, z_b1 + 60), 0), (x_sw, z_strip, 0), (H - Rp, z_strip, 0), (H - Rp, z_b1, 0)]
    if z_strip <= z_b1 + 5:          # no room for a strip over the sweep zone: the ribs end before it
        rib = [(x_pl0, z_b1, 0), (x_pl0, z_rt, 0), (x_sw, z_b1 + 60, 0), (x_sw, z_b1, 0)]
    poly = " ".join(f"{f(x)} {f(z)} {f(r)}" for x, z, r in rib)
    L = [
        "# LINK-1: J1 (ШМ-150м, ОПУ inner ring) -> J2 (ШМ-1000) - GENERATED by tools/link_gen.py 1",
        "# Coordinates: robot world frame at the zero pose (robot/RTC-7-layout.txt), mm.",
        "# Welded aluminium link: base plate over the whole ОПУ + J2 plate + 2 full-length ribs;",
        "# machining after welding: boss on the inner ring, J2 bore and its face, holes.",
        f"# J2 axis z={f(z2)}, J2 output face x={f(xf2)}, J2 base face (pilot {f(J2_BASE['pilot'])}h7) x={f(x_base)}.",
        f"# Ribs over the link-2 sweep zone (x >= {f(x_sw)}): top z={f(z_strip)} - link 2 + J3 pass over them",
        f"# with gap {f(g)} while J2 turns +-{f(P1['j2_range'])} deg (their lowest point there: z={zmin:.1f}).",
        "ASSEMBLY LINK-1",
        "DATA material=AlMg welded concept=1",
        "",
        "PART LINK-1-01_Weldment",
        "MOTION fixed",
        "DENSITY 2700",
        "COLOR 170 180 195",
        f"# base plate {f(2 * H)} x {f(2 * H)} x {f(P1['plate_t'])} over the whole ОПУ, {f(P1['boss_h'])} mm over the fixed outer ring",
        f"PRISM Z {f(z_b0)} {f(z_b1)} RPOLY {f(-H)} {f(-H)} {f(Rp)} {f(H)} {f(-H)} {f(Rp)} {f(H)} {f(H)} {f(Rp)} {f(-H)} {f(H)} {f(Rp)}",
        f"# machined boss on the ОПУ inner ring: D{f(P1['boss_D'])} (<= ds {f(OPU['ds'])}) x {f(P1['boss_h'])}",
        f"PRISM Z 0 {f(z_b0)} CIRC 0 0 {f(P1['boss_D'])}",
        f"CUT Z -1 {f(z_b1 + 1)} CIRC 0 0 {f(P1['bore'])}   # access to the J1 adapter screws",
        f"# J2 mounting plate (YZ plane) on the -X side of the J2 base face",
        f"PRISM X {f(x_pl0)} {f(x_pl1)} RPOLY {f(-hw)} {f(z_b1)} 0 {f(hw)} {f(z_b1)} 0 {f(hw)} {f(z_j2top)} {f(rc)} {f(-hw)} {f(z_j2top)} {f(rc)}",
        f"# ribs outside the J2 flange (D {f(2 * R2)}), over the whole plate length",
        f"PRISM Y {f(y_r0)} {f(y_r1)} RPOLY {poly}",
        f"PRISM Y {f(-y_r1)} {f(-y_r0)} RPOLY {poly}",
        f"# J2 bore: pilot {f(J2_BASE['pilot'])}H7 (the motor and the adapter plate of J2 pass through)",
        f"CUT X {f(x_pl0 - 1)} {f(x_pl1 + 1)} CIRC 0 {f(z2)} {f(J2_BASE['pilot'])}",
        f"TAP X {f(x_pl0)} {f(x_pl1)} 0 {f(z2)} {J2_BASE['n']} {f(J2_BASE['pcd'])} {J2_BASE['size']} {f(a_j2)}"
        "   # J2 flange screws from the output side",
        f"# 12 x M8 through the plate and the inner ring into the J1 adapter: D9 + head counterbore from the top",
        f"CUT Z -1 {f(z_b1 + 1)} PATTERN 0 0 {OPU['n']} {f(OPU['pcd'])} {f(OPU['hole'])} {f(OPU['ang'])}",
        f"CUT Z {f(z_b1 - P1['cbore_depth'])} {f(z_b1 + 1)} PATTERN 0 0 {OPU['n']} {f(OPU['pcd'])} "
        f"{f(P1['cbore_D'])} {f(OPU['ang'])}",
        f"PORTP j1_ring Z 0 -1 role=on_opu_inner_ring screws=12xM8_D139 boss=D{f(P1['boss_D'])}",
        f"PORTP j2_base X {f(x_base)} 1 role=j2_housing fit={f(J2_BASE['pilot'])}H7 bolts={J2_BASE['n']}x{J2_BASE['size']}_D{f(J2_BASE['pcd'])}",
        "END",
        "",
        "PART LINK-1-02_J1Adapter",
        "MOTION fixed",
        "DENSITY 2700",
        "COLOR 120 130 150",
        f"# under the ОПУ inner ring (z {f(z_ad0)}..{f(z_ad1)}), D {f(P1['adapter_D'])}; recess on the KB32 output spigot",
        f"PRISM Z {f(z_ad0)} {f(z_ad1)} CIRC 0 0 {f(P1['adapter_D'])}",
        f"CUT Z {f(z_ad0 - 1)} {f(z_face1)} CIRC 0 0 {f(KB32_OUT['fit'])}   # recess {f(KB32_OUT['fit'])}H7 x {f(P1['adapter_recess'])}",
        f"CUT Z {f(z_face1 - 1)} {f(z_ad1 + 1)} CIRC 0 0 {f(P1['adapter_hole'])}   # clears the clamp flange of the J1 input shaft",
        f"CUT Z {f(z_face1 - 1)} {f(z_ad1 + 1)} PATTERN 0 0 {KB32_OUT['n']} {f(KB32_OUT['pcd'])} {f(KB32_OUT['hole'])} "
        f"{f(plane_angle((0, 0, 1), KB32_OUT['ang'], 'Z'))}   # 16 x M5 into the KB32 output, heads on top (reached through the plate bore)",
        f"TAP Z {f(z_ad0)} {f(z_ad1)} 0 0 {OPU['n']} {f(OPU['pcd'])} M8 {f(OPU['ang'])}   # the 12 ring screws",
        f"PORTP j1_output Z {f(z_face1)} -1 role=on_kb32_output fit={f(KB32_OUT['fit'])}H7 bolts=16xM5_D100",
        f"PORTP ring Z {f(z_ad1)} 1 role=under_opu_inner_ring",
        "END",
    ]
    print(f"ribs: J2 +-{P1['j2_range']:g} deg -> link 2 / J3 lowest z {zmin:.1f} in the rib band; rib top there {z_strip:.1f} "
          f"({z_strip - z_b1:.1f} over the plate)", file=sys.stderr)
    return "\n".join(L) + "\n"


def link2(lay):
    """Link 2: J2 output (80E) -> J3 base (ШМ-500 motor-housing flange), welded aluminium."""
    ax = {a["name"]: a for a in lay["axes"]}
    env = je.all_joints()
    E2, E3 = env["SHM-1000"], env["SHM-500"]
    j2, j3 = ax["J2"], ax["J3"]
    z2, xf2 = j2["p"][2], j2["face"][0]
    x3 = j3["p"][0]
    # J3 joint frame along +Z: joint x -> world z = face_z - x_out + x
    z3 = lambda xj: j3["face"][2] - E3["x_out"] + xj
    z_base3 = z3(E3["x_base"])                      # J3 base face (link side, toward the motor)
    t, H = P2["plate_t"], P2["half"]
    x_p0, x_p1 = xf2, xf2 + t
    z_sh0, z_sh1 = z_base3 - P2["shelf_t"], z_base3
    x_sh1 = x3 + H
    w0, w1 = H - P2["wall_t"], H
    z_rear3 = z3(E3["x_rear"])
    housing_end = xf2 - (E2["x_out"] - max(x1 for x0, x1, r, n in E2["fixed"]))   # J2 housing face (world x)
    skirt0 = xf2 - P2["skirt_len"]
    assert skirt0 > housing_end + 2, f"skirt {skirt0} too close to the J2 housing {housing_end}"
    wall = (f"{f(x_p1)} {f(z2)} 0 {f(x_p1)} {f(z_sh0)} 0 "
            f"{f(x_sh1 - P2['shelf_R'])} {f(z_sh0)} 0")      # plain gusset; ends before the rounded shelf corner
    a2 = lambda a: plane_angle((1, 0, 0), a, "X")   # J2 joint angle -> (y, z) plane angle
    a3 = plane_angle((0, 0, 1), J3_BASE["ang_joint"], "Z")   # J3 joint angle -> (x, y) plane angle
    L = [
        "# LINK-2: J2 (ШМ-1000 output) -> J3 (ШМ-500 base) - GENERATED by tools/link_gen.py 2",
        "# Coordinates: robot world frame at the zero pose (robot/RTC-7-layout.txt), mm.",
        "# Welded aluminium: plate on the J2 output (round below the J2 axis - it turns over link 1),",
        "# shelf under the J3 flange, two side walls; the space under J3 stays open for the cable loop.",
        f"# J2 axis z={f(z2)}, output face x={f(xf2)} (housing ends at x={f(housing_end)}); "
        f"J3 axis x={f(x3)}, J3 base face z={f(z_base3)}, J3 rear end z={f(z_rear3)}.",
        "ASSEMBLY LINK-2",
        "DATA material=AlMg welded concept=1",
        "",
        "PART LINK-2-01_Weldment",
        "MOTION fixed",
        "DENSITY 2700",
        "COLOR 175 195 170",
        f"# plate on the J2 output: disc R{f(P2['disc_R'])} round the J2 axis + rectangle up to the J3 shelf",
        f"PRISM X {f(x_p0)} {f(x_p1)} CIRC 0 {f(z2)} {f(2 * P2['disc_R'])}",
        f"PRISM X {f(x_p0)} {f(x_p1)} RECT {f(-H)} {f(H)} {f(z2)} {f(z_sh1)}",
        f"# centring skirt on the J2 output D{f(J2_OUT['fit'])}h7 (recess {f(J2_OUT['fit'])}H7 x {f(P2['skirt_len'])})",
        f"PRISM X {f(skirt0)} {f(x_p0)} RING 0 {f(z2)} {f(P2['skirt_D'])} {f(J2_OUT['fit'])}",
        f"# J3 shelf under the J3 flange D{f(J3_BASE['flange_D'])}: bore {f(J3_BASE['pilot'])}H7 for the pilot (the J3 motor hangs below)",
        f"PRISM Z {f(z_sh0)} {f(z_sh1)} RPOLY {f(x_p0)} {f(-H)} 0 {f(x_sh1)} {f(-H)} {f(P2['shelf_R'])} {f(x_sh1)} {f(H)} {f(P2['shelf_R'])} {f(x_p0)} {f(H)} 0",
        f"CUT Z {f(z_sh0 - 1)} {f(z_sh1 + 1)} CIRC {f(x3)} 0 {f(J3_BASE['pilot'])}",
        f"TAP Z {f(z_sh0)} {f(z_sh1)} {f(x3)} 0 {J3_BASE['n']} {f(J3_BASE['pcd'])} {J3_BASE['size']} {f(a3)}"
        "   # J3: screws from the top through the reducer and the motor housing",
        "# side walls from the plate (not below the J2 axis - they turn over link 1) to the end of the shelf;",
        "# outside the J3 motor, open below for the cable",
        f"PRISM Y {f(w0)} {f(w1)} RPOLY {wall}",
        f"PRISM Y {f(-w1)} {f(-w0)} RPOLY {wall}",
        "# J2 output screws (heads on the +X side) and access to the 3 Rc1/8 plugs",
    ]
    for a in J2_OUT["m8"][1]:
        L.append(f"CUT X {f(skirt0 - 1)} {f(x_p1 + 1)} PATTERN 0 {f(z2)} 3 {f(J2_OUT['m8'][0])} 9 {f(a2(a))}   # M8 at {f(a)} deg (joint)")
    for a in J2_OUT["m10"][1]:
        L.append(f"CUT X {f(skirt0 - 1)} {f(x_p1 + 1)} PATTERN 0 {f(z2)} 3 {f(J2_OUT['m10'][0])} 11 {f(a2(a))}   # M10 at {f(a)} deg (joint)")
    L.append(f"CUT X {f(skirt0 - 1)} {f(x_p1 + 1)} PATTERN 0 {f(z2)} 3 {f(J2_OUT['plug'][0])} 12 {f(a2(J2_OUT['plug'][1]))}   # plugs")
    L += [
        f"PORTP j2_out X {f(xf2)} -1 role=on_j2_output fit={f(J2_OUT['fit'])}H7 bolts=9xM8_D142+6xM10_D110",
        f"PORTP j3_base Z {f(z_base3)} 1 role=j3_housing fit={f(J3_BASE['pilot'])}H7 bolts={J3_BASE['n']}x{J3_BASE['size']}_D{f(J3_BASE['pcd'])}",
        "END",
    ]
    return "\n".join(L) + "\n"


def link3(lay):
    """Link 3 (upper arm): J3 output (KB45) -> J4 base (ШМ-500 motor-housing flange), welded aluminium:
    flange with a centring skirt on the J3 output, tube on the J3 axis (cable inside), head box that
    holds J4 by its flange and encloses the J4 motor end and the cable bend J3 -> J4."""
    ax = {a["name"]: a for a in lay["axes"]}
    E4 = je.all_joints()["SHM-500"]
    j3, j4 = ax["J3"], ax["J4"]
    x3, z_f3 = j3["p"][0], j3["face"][2]
    z4, xf4 = j4["p"][2], j4["face"][0]
    # J4 along -X: joint x -> world x = face + (x_out - x)
    wx = lambda xj: xf4 + (E4["x_out"] - xj)
    x_base4 = wx(E4["x_base"])                     # J4 base face (flange), the link on its motor (+X) side
    x_rear4 = wx(E4["x_rear"])                     # J4 rear end (cover) - the cable enters here
    t = P3
    s0 = z_f3 - t["skirt_len"]
    zf1 = z_f3 + t["flange_t"]
    hb, bt = t["box_half"], t["box_t"]
    xp0, xp1 = x_base4, x_base4 + t["plate_t"]
    xb1 = x3 + t["tube_D"] / 2 + bt                # box end wall outside the tube
    zb0, zb1 = z4 - hb, z4 + hb                     # box bottom / top (outer)
    ph = t["plate_half"]
    rmot = max(r for x0, x1, r, n in E4["fixed"] if n in ("motor",) or "StatorClamp" in n)
    assert hb - bt > rmot + 5, f"box inner half {hb - bt} vs J4 motor radius {rmot}"
    assert x_rear4 < xb1 - bt - 5, "the J4 rear end must be inside the head box"
    a3 = plane_angle((0, 0, 1), KB45_OUT["ang"], "Z")
    a4 = plane_angle((-1, 0, 0), J3_BASE["ang_joint"], "X")
    R, Rb = t["plate_R"], t["box_R"]
    L = [
        "# LINK-3 (upper arm): J3 (ШМ-500 output) -> J4 (ШМ-500 base) - GENERATED by tools/link_gen.py 3",
        "# Coordinates: robot world frame at the zero pose (robot/RTC-7-layout.txt), mm.",
        "# Welded aluminium: flange + skirt on the J3 output, tube D%g x %g on the J3 axis (cable inside)," % (t["tube_D"], t["tube_t"]),
        "# head box enclosing the J4 motor end and the cable bend; J4 on the mounting plate (pilot 168H7).",
        f"# J3 output face z={f(z_f3)}; J4 axis z={f(z4)}, J4 base face x={f(x_base4)}, J4 rear end x={f(x_rear4)}.",
        "ASSEMBLY LINK-3",
        "DATA material=AlMg welded concept=1",
        "",
        "PART LINK-3-01_Weldment",
        "MOTION fixed",
        "DENSITY 2700",
        "COLOR 200 185 150",
        f"# flange on the J3 output with a centring skirt (recess {f(KB45_OUT['fit'])}H7 x {f(t['skirt_len'])})",
        f"PRISM Z {f(s0)} {f(z_f3)} RING {f(x3)} 0 {f(t['skirt_D'])} {f(KB45_OUT['fit'])}",
        f"PRISM Z {f(z_f3)} {f(zf1)} CIRC {f(x3)} 0 {f(t['skirt_D'])}",
        f"CUT Z {f(z_f3 - 1)} {f(zf1 + 1)} CIRC {f(x3)} 0 {f(t['flange_hole'])}   # cable",
        f"CUT Z {f(z_f3 - 1)} {f(zf1 + 1)} PATTERN {f(x3)} 0 {KB45_OUT['n']} {f(KB45_OUT['pcd'])} {f(KB45_OUT['hole'])} {f(a3)}"
        "   # 16 x M8 into the J3 output, heads outside the tube",
        f"# upper-arm tube D{f(t['tube_D'])} x {f(t['tube_t'])} on the J3 axis, from the flange into the head box",
        f"PRISM Z {f(zf1)} {f(zb0 + bt)} RING {f(x3)} 0 {f(t['tube_D'])} {f(t['tube_D'] - 2 * t['tube_t'])}",
        f"# J4 mounting plate (YZ) on the motor side of the J4 flange: bore {f(J3_BASE['pilot'])}H7, 9 x M6 on D{f(J3_BASE['pcd'])}",
        f"PRISM X {f(xp0)} {f(xp1)} RPOLY {f(-ph)} {f(z4 - ph)} {f(R)} {f(ph)} {f(z4 - ph)} {f(R)} {f(ph)} {f(z4 + ph)} {f(R)} {f(-ph)} {f(z4 + ph)} {f(R)}"
        "   # square round the J4 axis, wider than the J4 flange D190",
        f"CUT X {f(xp0 - 1)} {f(xp1 + 1)} CIRC 0 {f(z4)} {f(J3_BASE['pilot'])}",
        f"TAP X {f(xp0)} {f(xp1)} 0 {f(z4)} {J3_BASE['n']} {f(J3_BASE['pcd'])} {J3_BASE['size']} {f(a4)}   # J4: screws from the output side",
        f"# head box x {f(xp1)}..{f(xb1)}, y +-{f(hb)}, z {f(zb0)}..{f(zb1)}: walls {f(bt)}, end wall removable (access to the J4 sensors)",
        f"PRISM Y {f(hb - bt)} {f(hb)} RPOLY {f(xp1)} {f(zb0)} 0 {f(xb1)} {f(zb0)} {f(Rb)} {f(xb1)} {f(zb1)} {f(Rb)} {f(xp1)} {f(zb1)} 0",
        f"PRISM Y {f(-hb)} {f(-hb + bt)} RPOLY {f(xp1)} {f(zb0)} 0 {f(xb1)} {f(zb0)} {f(Rb)} {f(xb1)} {f(zb1)} {f(Rb)} {f(xp1)} {f(zb1)} 0",
        f"PRISM Z {f(zb1 - bt)} {f(zb1)} RPOLY {f(xp1)} {f(-hb)} 0 {f(xb1)} {f(-hb)} {f(Rb)} {f(xb1)} {f(hb)} {f(Rb)} {f(xp1)} {f(hb)} 0",
        f"PRISM Z {f(zb0)} {f(zb0 + bt)} RPOLY {f(xp1)} {f(-hb)} 0 {f(xb1)} {f(-hb)} {f(Rb)} {f(xb1)} {f(hb)} {f(Rb)} {f(xp1)} {f(hb)} 0",
        f"CUT Z {f(zb0 - 1)} {f(zb0 + bt + 1)} CIRC {f(x3)} 0 {f(t['tube_D'] - 2 * t['tube_t'])}   # tube into the box",
        f"PRISM X {f(xb1 - bt)} {f(xb1)} RPOLY {f(-hb)} {f(zb0)} {f(Rb)} {f(hb)} {f(zb0)} {f(Rb)} {f(hb)} {f(zb1)} {f(Rb)} {f(-hb)} {f(zb1)} {f(Rb)}",
        f"PORTP j3_out Z {f(z_f3)} -1 role=on_j3_output fit={f(KB45_OUT['fit'])}H7 bolts=16xM8_D140",
        f"PORTP j4_base X {f(x_base4)} 1 role=j4_housing fit={f(J3_BASE['pilot'])}H7 bolts={J3_BASE['n']}x{J3_BASE['size']}_D{f(J3_BASE['pcd'])}",
        "END",
    ]
    return "\n".join(L) + "\n"


def link4(lay):
    """Link 4: J4 output (KB45, toward -X) -> J5 base (ШМ-150 flange), welded aluminium; the mirror of
    link 2: plate with a centring skirt on the J4 output (cable hole), shelf under the J5 flange,
    side walls; open below for the cable bend J4 -> J5."""
    ax = {a["name"]: a for a in lay["axes"]}
    env = je.all_joints()
    E4, E5 = env["SHM-500"], env["SHM-150"]
    j4, j5 = ax["J4"], ax["J5"]
    z4, xf4 = j4["p"][2], j4["face"][0]
    x5 = j5["p"][0]
    z5 = lambda xj: j5["face"][2] - E5["x_out"] + xj
    z_base5 = z5(E5["x_base"])
    t, H = P4["plate_t"], P4["half"]
    xp0, xp1 = xf4 - t, xf4                         # plate on the J4 output face (output toward -X)
    zs0, zs1 = z_base5 - P4["shelf_t"], z_base5
    xs0 = x5 - H                                    # far end of the shelf
    sk1 = xf4 + P4["skirt_len"]
    housing_end = xf4 + (E4["x_out"] - max(x1 for x0, x1, r, n in E4["fixed"]))
    assert sk1 < housing_end - 2, f"skirt {sk1} too close to the J4 housing {housing_end}"
    a4 = plane_angle((-1, 0, 0), KB45_OUT["ang"], "X")
    a5 = plane_angle((0, 0, 1), J5_BASE["ang_joint"], "Z")
    R = P4["shelf_R"]
    wall = f"{f(xp0)} {f(z4)} 0 {f(xp0)} {f(zs0)} 0 {f(xs0 + R)} {f(zs0)} 0"
    L = [
        "# LINK-4: J4 (ШМ-500 output) -> J5 (ШМ-150 base) - GENERATED by tools/link_gen.py 4",
        "# Coordinates: robot world frame at the zero pose (robot/RTC-7-layout.txt), mm.",
        "# Welded aluminium: plate on the J4 output (skirt, cable hole), shelf under the J5 flange, side walls;",
        "# the cable leaves the J4 output, bends up (R40) under the shelf into the J5 rear end.",
        f"# J4 axis z={f(z4)}, J4 output face x={f(xf4)}; J5 axis x={f(x5)}, J5 base face z={f(z_base5)}.",
        "ASSEMBLY LINK-4",
        "DATA material=AlMg welded concept=1",
        "",
        "PART LINK-4-01_Weldment",
        "MOTION fixed",
        "DENSITY 2700",
        "COLOR 185 170 200",
        f"# plate on the J4 output: disc R{f(P4['disc_R'])} round the J4 axis + rectangle up to the J5 shelf",
        f"PRISM X {f(xp0)} {f(xp1)} CIRC 0 {f(z4)} {f(2 * P4['disc_R'])}",
        f"PRISM X {f(xp0)} {f(xp1)} RECT {f(-H)} {f(H)} {f(z4)} {f(zs1)}",
        f"PRISM X {f(xp1)} {f(sk1)} RING 0 {f(z4)} {f(P4['skirt_D'])} {f(KB45_OUT['fit'])}   # centring skirt {f(KB45_OUT['fit'])}H7",
        f"CUT X {f(xp0 - 1)} {f(sk1 + 1)} CIRC 0 {f(z4)} {f(P4['cable_hole'])}   # cable",
        f"CUT X {f(xp0 - 1)} {f(sk1 + 1)} PATTERN 0 {f(z4)} {KB45_OUT['n']} {f(KB45_OUT['pcd'])} {f(KB45_OUT['hole'])} {f(a4)}"
        "   # 16 x M8 into the J4 output, heads on the -X side",
        f"# J5 shelf under the J5 flange D{f(J5_BASE['flange_D'])}: bore {f(J5_BASE['pilot'])}H7, 12 x M5 on D{f(J5_BASE['pcd'])}",
        f"PRISM Z {f(zs0)} {f(zs1)} RPOLY {f(xp1)} {f(-H)} 0 {f(xs0)} {f(-H)} {f(R)} {f(xs0)} {f(H)} {f(R)} {f(xp1)} {f(H)} 0",
        f"CUT Z {f(zs0 - 1)} {f(zs1 + 1)} CIRC {f(x5)} 0 {f(J5_BASE['pilot'])}",
        f"TAP Z {f(zs0)} {f(zs1)} {f(x5)} 0 {J5_BASE['n']} {f(J5_BASE['pcd'])} {J5_BASE['size']} {f(a5)}   # J5: screws from the top",
        "# side walls (plain gussets), open below for the cable bend",
        f"PRISM Y {f(H - P4['wall_t'])} {f(H)} RPOLY {wall}",
        f"PRISM Y {f(-H)} {f(-H + P4['wall_t'])} RPOLY {wall}",
        f"PORTP j4_out X {f(xf4)} 1 role=on_j4_output fit={f(KB45_OUT['fit'])}H7 bolts=16xM8_D140",
        f"PORTP j5_base Z {f(z_base5)} 1 role=j5_housing fit={f(J5_BASE['pilot'])}H7 bolts={J5_BASE['n']}x{J5_BASE['size']}_D{f(J5_BASE['pcd'])}",
        "END",
    ]
    return "\n".join(L) + "\n"


def link5(lay):
    """Link 5 (forearm): J5 output (KB32) -> J6 base (ШМ-150 flange, J6 along +X), welded aluminium:
    flange + skirt on the J5 output, tube on the J5 axis (cable inside; the M5 heads stay outside it),
    head box round the J6 motor end and the cable bend J5 -> J6, J6 mounting plate."""
    ax = {a["name"]: a for a in lay["axes"]}
    E6 = je.all_joints()["SHM-150"]
    j5, j6 = ax["J5"], ax["J6"]
    x5, z_f5 = j5["p"][0], j5["face"][2]
    z6, xf6 = j6["p"][2], j6["face"][0]
    wx = lambda xj: xf6 - (E6["x_out"] - xj)        # J6 along +X: joint x -> world x
    x_base6, x_rear6 = wx(E6["x_base"]), wx(E6["x_rear"])
    t = P5
    s0 = z_f5 - t["skirt_len"]
    zf1 = z_f5 + t["flange_t"]
    hb, bt = t["box_half"], t["box_t"]
    xp0, xp1 = x_base6 - t["plate_t"], x_base6        # plate on the motor (-X) side of the J6 flange
    xb0 = x5 - t["tube_D"] / 2 - bt - 3.0               # box end wall outside the tube, 3 mm clear (no tangent contact)
    zb0, zb1 = z6 - hb, z6 + hb
    ph, R, Rb = t["plate_half"], t["plate_R"], t["box_R"]
    head_r = KB32_OUT2["pcd"] / 2 - 2.75 - 4.25         # inner edge of the M5 heads
    assert t["tube_D"] / 2 < head_r, "the J5 output screw heads must stay outside the tube"
    assert x_rear6 > xb0 + bt + 5, "the J6 rear end must be inside the head box"
    a5 = plane_angle((0, 0, 1), KB32_OUT2["ang"], "Z")
    a6 = plane_angle((1, 0, 0), J5_BASE["ang_joint"], "X")
    L = [
        "# LINK-5 (forearm): J5 (ШМ-150 output) -> J6 (ШМ-150 base) - GENERATED by tools/link_gen.py 5",
        "# Coordinates: robot world frame at the zero pose (robot/RTC-7-layout.txt), mm.",
        f"# Welded aluminium: flange + skirt on the J5 output, tube D{f(t['tube_D'])} x {f(t['tube_t'])} on the J5 axis "
        "(cable inside), head box round the J6 motor end and the cable bend, J6 mounting plate (pilot 122H7).",
        f"# J5 output face z={f(z_f5)}; J6 axis z={f(z6)}, J6 base face x={f(x_base6)}, J6 rear end x={f(x_rear6)}.",
        "ASSEMBLY LINK-5",
        "DATA material=AlMg welded concept=1",
        "",
        "PART LINK-5-01_Weldment",
        "MOTION fixed",
        "DENSITY 2700",
        "COLOR 200 185 150",
        f"PRISM Z {f(s0)} {f(z_f5)} RING {f(x5)} 0 {f(t['skirt_D'])} {f(KB32_OUT2['fit'])}   # centring skirt {f(KB32_OUT2['fit'])}H7",
        f"PRISM Z {f(z_f5)} {f(zf1)} CIRC {f(x5)} 0 {f(t['flange_D'])}",
        f"CUT Z {f(s0 - 1)} {f(zf1 + 1)} CIRC {f(x5)} 0 {f(t['flange_hole'])}   # cable",
        f"CUT Z {f(z_f5 - 1)} {f(zf1 + 1)} PATTERN {f(x5)} 0 {KB32_OUT2['n']} {f(KB32_OUT2['pcd'])} {f(KB32_OUT2['hole'])} {f(a5)}"
        "   # 16 x M5 into the J5 output, heads outside the tube",
        f"PRISM Z {f(zf1)} {f(zb0 + bt)} RING {f(x5)} 0 {f(t['tube_D'])} {f(t['tube_D'] - 2 * t['tube_t'])}   # forearm tube",
        f"PRISM X {f(xp0)} {f(xp1)} RPOLY {f(-ph)} {f(z6 - ph)} {f(R)} {f(ph)} {f(z6 - ph)} {f(R)} {f(ph)} {f(z6 + ph)} {f(R)} {f(-ph)} {f(z6 + ph)} {f(R)}"
        "   # J6 mounting plate, wider than the J6 flange D142",
        f"CUT X {f(xp0 - 1)} {f(xp1 + 1)} CIRC 0 {f(z6)} {f(J5_BASE['pilot'])}",
        f"TAP X {f(xp0)} {f(xp1)} 0 {f(z6)} {J5_BASE['n']} {f(J5_BASE['pcd'])} {J5_BASE['size']} {f(a6)}   # J6: screws from the output side",
        f"# head box x {f(xb0)}..{f(xp0)}, y +-{f(hb)}, z {f(zb0)}..{f(zb1)}; end wall removable (access to the J6 sensors)",
        f"PRISM Y {f(hb - bt)} {f(hb)} RPOLY {f(xp0)} {f(zb0)} 0 {f(xb0)} {f(zb0)} {f(Rb)} {f(xb0)} {f(zb1)} {f(Rb)} {f(xp0)} {f(zb1)} 0",
        f"PRISM Y {f(-hb)} {f(-hb + bt)} RPOLY {f(xp0)} {f(zb0)} 0 {f(xb0)} {f(zb0)} {f(Rb)} {f(xb0)} {f(zb1)} {f(Rb)} {f(xp0)} {f(zb1)} 0",
        f"PRISM Z {f(zb1 - bt)} {f(zb1)} RPOLY {f(xp0)} {f(-hb)} 0 {f(xb0)} {f(-hb)} {f(Rb)} {f(xb0)} {f(hb)} {f(Rb)} {f(xp0)} {f(hb)} 0",
        f"PRISM Z {f(zb0)} {f(zb0 + bt)} RPOLY {f(xp0)} {f(-hb)} 0 {f(xb0)} {f(-hb)} {f(Rb)} {f(xb0)} {f(hb)} {f(Rb)} {f(xp0)} {f(hb)} 0",
        f"CUT Z {f(zb0 - 1)} {f(zb0 + bt + 1)} CIRC {f(x5)} 0 {f(t['tube_D'] - 2 * t['tube_t'])}   # tube into the box",
        f"PRISM X {f(xb0)} {f(xb0 + bt)} RPOLY {f(-hb)} {f(zb0)} {f(Rb)} {f(hb)} {f(zb0)} {f(Rb)} {f(hb)} {f(zb1)} {f(Rb)} {f(-hb)} {f(zb1)} {f(Rb)}",
        f"PORTP j5_out Z {f(z_f5)} -1 role=on_j5_output fit={f(KB32_OUT2['fit'])}H7 bolts=16xM5_D100",
        f"PORTP j6_base X {f(x_base6)} -1 role=j6_housing fit={f(J5_BASE['pilot'])}H7 bolts={J5_BASE['n']}x{J5_BASE['size']}_D{f(J5_BASE['pcd'])}",
        "END",
    ]
    return "\n".join(L) + "\n"


def link6(lay):
    """Link 6: J6 output (KB32, toward +X) -> J7 base (ШМ-60 flange), welded aluminium; like link 2:
    plate with a centring skirt on the J6 output (cable hole), shelf under the J7 flange, side walls."""
    ax = {a["name"]: a for a in lay["axes"]}
    env = je.all_joints()
    E6, E7 = env["SHM-150"], env["SHM-60"]
    j6, j7 = ax["J6"], ax["J7"]
    z6, xf6 = j6["p"][2], j6["face"][0]
    x7 = j7["p"][0]
    z_base7 = j7["face"][2] - E7["x_out"] + E7["x_base"]
    t, H = P6["plate_t"], P6["half"]
    xp0, xp1 = xf6, xf6 + t
    zs0, zs1 = z_base7 - P6["shelf_t"], z_base7
    xs1 = x7 + H
    sk0 = xf6 - P6["skirt_len"]
    housing_end = xf6 - (E6["x_out"] - max(x1 for x0, x1, r, n in E6["fixed"]))
    assert sk0 > housing_end + 2, f"skirt {sk0} too close to the J6 housing {housing_end}"
    a6 = plane_angle((1, 0, 0), KB32_OUT2["ang"], "X")
    a7 = plane_angle((0, 0, 1), J7_BASE["ang_joint"], "Z")
    R = P6["shelf_R"]
    wall = f"{f(xp1)} {f(z6)} 0 {f(xp1)} {f(zs0)} 0 {f(xs1 - R)} {f(zs0)} 0"
    L = [
        "# LINK-6: J6 (ШМ-150 output) -> J7 (ШМ-60 base) - GENERATED by tools/link_gen.py 6",
        "# Coordinates: robot world frame at the zero pose (robot/RTC-7-layout.txt), mm.",
        "# Welded aluminium: plate on the J6 output (skirt, cable hole), shelf under the J7 flange, side walls;",
        "# the cable leaves the J6 output, bends up (R32) under the shelf into the J7 rear end.",
        f"# J6 axis z={f(z6)}, J6 output face x={f(xf6)}; J7 axis x={f(x7)}, J7 base face z={f(z_base7)}.",
        "ASSEMBLY LINK-6",
        "DATA material=AlMg welded concept=1",
        "",
        "PART LINK-6-01_Weldment",
        "MOTION fixed",
        "DENSITY 2700",
        "COLOR 185 170 200",
        f"PRISM X {f(xp0)} {f(xp1)} CIRC 0 {f(z6)} {f(2 * P6['disc_R'])}",
        f"PRISM X {f(xp0)} {f(xp1)} RECT {f(-H)} {f(H)} {f(z6)} {f(zs1)}",
        f"PRISM X {f(sk0)} {f(xp0)} RING 0 {f(z6)} {f(P6['skirt_D'])} {f(KB32_OUT2['fit'])}   # centring skirt {f(KB32_OUT2['fit'])}H7",
        f"CUT X {f(sk0 - 1)} {f(xp1 + 1)} CIRC 0 {f(z6)} {f(P6['cable_hole'])}   # cable",
        f"CUT X {f(sk0 - 1)} {f(xp1 + 1)} PATTERN 0 {f(z6)} {KB32_OUT2['n']} {f(KB32_OUT2['pcd'])} {f(KB32_OUT2['hole'])} {f(a6)}"
        "   # 16 x M5 into the J6 output, heads on the +X side",
        f"PRISM Z {f(zs0)} {f(zs1)} RPOLY {f(xp0)} {f(-H)} 0 {f(xs1)} {f(-H)} {f(R)} {f(xs1)} {f(H)} {f(R)} {f(xp0)} {f(H)} 0"
        f"   # J7 shelf under the J7 flange D{f(J7_BASE['flange_D'])}",
        f"CUT Z {f(zs0 - 1)} {f(zs1 + 1)} CIRC {f(x7)} 0 {f(J7_BASE['pilot'])}",
        f"TAP Z {f(zs0)} {f(zs1)} {f(x7)} 0 {J7_BASE['n']} {f(J7_BASE['pcd'])} {J7_BASE['size']} {f(a7)}   # J7: screws from the top",
        f"PRISM Y {f(H - P6['wall_t'])} {f(H)} RPOLY {wall}",
        f"PRISM Y {f(-H)} {f(-H + P6['wall_t'])} RPOLY {wall}",
        f"PORTP j6_out X {f(xf6)} -1 role=on_j6_output fit={f(KB32_OUT2['fit'])}H7 bolts=16xM5_D100",
        f"PORTP j7_base Z {f(z_base7)} 1 role=j7_housing fit={f(J7_BASE['pilot'])}H7 bolts={J7_BASE['n']}x{J7_BASE['size']}_D{f(J7_BASE['pcd'])}",
        "END",
    ]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("link", type=int)
    ap.add_argument("--layout", default=os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    a = ap.parse_args()
    lay = rs.read_layout(a.layout)
    gen = {1: link1, 2: link2, 3: link3, 4: link4, 5: link5, 6: link6}
    if a.link not in gen:
        sys.exit("links 1..6")
    txt = gen[a.link](lay)
    d = os.path.join(ROOT, "links", f"LINK-{a.link}")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, f"LINK-{a.link}.txt")
    open(out, "w", encoding="utf-8").write(txt)
    print(txt)
    print("->", out)


if __name__ == "__main__":
    main()
