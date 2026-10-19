#!/usr/bin/env python3
"""Export of the arm to URDF (+ STL meshes) for MATLAB / Simscape Multibody (smimport), ROS, PyBullet.

    python tools/urdf_export.py [--layout robot/RTC-7-layout.txt] [--out sim/RTC-7] [--payload 8]

What goes out (sim/RTC-7/):
  * RTC-7.urdf - base_link (ОПУ outer ring + J1 housing, fixed to the world) and link_1 .. link_7,
    revolute joints J1 .. J7, a fixed "tool" body (gripper visual + payload mass) and a massless "tcp"
    frame; units m, kg, kg*m^2; at the zero pose every link frame is parallel to the world frame and
    sits on its joint axis (the axis point of tools/robot_scheme.py), the joint axis is the layout
    direction - so the joint angles are the same as in the viewer / SolidWorks animation;
  * meshes/<link>.stl - all the bodies of that link (designed link parts, joint parts of that side,
    ОПУ rings, assumed tool) in the link frame, metres;
  * RTC-7-bodies.csv - mass, centre of mass and inertia of every link (also in the URDF);
  * RTC-7-demo-traj.csv - the demo program (robot/RTC-7-demo.txt) as joint angles, rad, 30 fps.

Mass model = tools/robot_statics.py: links - designed parts, volume x DENSITY; joints - catalog
masses split into the housing + motor side (previous link) and the output shaft (next link), spread
over the revolved part profiles of that side by volume (inertia from the same profiles); ОПУ inner ring
steel; tool-change interface --iface kg (4); payload --payload kg, a small block with its centre of
mass --payload-com mm beyond the flange (100). ASSUMED: motor rotor inertia (reflected through the
reducer) and joint friction are NOT in the URDF - add them on the joints in Simscape
(sim/RTC-7/rtc7_build.m: internal mechanics).
"""
import argparse
import csv
import math
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_envelope as je  # noqa: E402
import link_build as lb  # noqa: E402
import robot_anim as ra  # noqa: E402
import robot_scheme as rs  # noqa: E402
import robot_statics as st  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST, AL = 7850.0, 2700.0

# colours for the URDF materials (r g b), same palette as the viewer
RGB = {"link": (0.906, 0.890, 0.855), "joint": (0.239, 0.263, 0.294), "output": (0.663, 0.694, 0.729),
       "motor": (0.145, 0.157, 0.173), "opu": (0.490, 0.522, 0.561), "tool": (0.910, 0.455, 0.184)}


def props(shape):
    """(volume mm^3, centre mm, inertia about the centre mm^5) for unit density."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    c = g.CentreOfMass()
    M = g.MatrixOfInertia()
    I = np.array([[M.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)])
    return g.Mass(), np.array([c.X(), c.Y(), c.Z()]), I


def add_mass(acc, m, c, Ic):
    """acc = [m, sum m c, list of (m, c, Ic)] - combined later about the joint COM."""
    acc[0] += m
    acc[1] += m * c
    acc[2].append((m, c, Ic))


def combine(acc):
    m = acc[0]
    if m <= 0:
        return 0.0, np.zeros(3), np.zeros((3, 3))
    com = acc[1] / m
    I = np.zeros((3, 3))
    for mi, ci, Ici in acc[2]:
        d = ci - com
        I += Ici + mi * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    return m, com, I


def box_inertia(m, a, b, c):
    return m / 12.0 * np.diag([b * b + c * c, a * a + c * c, a * a + b * b])


def kind_of(name):
    n = name.lower()
    if n.startswith("l") and " " in n and n.split()[0][1:].isdigit():
        return "link"
    if "оп" in n or "opu" in n:
        return "opu"
    if "assumed" in n:
        return "tool"
    if "outputshaft" in n:
        return "output"
    if "motor" in n and "housing" not in n:
        return "motor"
    return "joint"


def write_stl(path, tris):
    """Binary STL of an (n, 3, 3) float array."""
    with open(path, "wb") as f:
        f.write(b"RTC-7 urdf_export".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            n = np.cross(t[1] - t[0], t[2] - t[0])
            ln = np.linalg.norm(n)
            n = n / ln if ln > 0 else n
            f.write(struct.pack("<12fH", *n, *t[0], *t[1], *t[2], 0))


def build(lay, payload, payload_com, iface, tool_len):
    """Per link (0 = base .. 7): shapes, mass properties (world frame at the zero pose, mm / kg)."""
    n = len(lay["axes"])
    bl = ra.bodies(lay, tool_len)              # (name, group, colour, shape) - the viewer geometry
    groups = {g: {"shapes": [], "acc": [0.0, np.zeros(3), []]} for g in range(n + 1)}
    tool_vis = []
    # joint side masses (catalog): housing + motor -> group i, output shaft -> group i + 1
    side_mass, notes = {}, []
    for i, a in enumerate(lay["axes"]):
        name = a["joint"] if os.path.isdir(os.path.join(ROOT, "joints", a["joint"])) else a["joint"].rstrip("m")
        mf, _, mo, _, nn = st.joint_masses(name)
        notes += nn
        side_mass[(a["name"], "fixed")] = mf
        side_mass[(a["name"], "out")] = mo
    # volumes of every joint side, to spread its mass
    side_vol = {}
    pr = []
    for nm, g, col, shp in bl:
        v, c, I = props(shp)
        pr.append((v, c, I))
        jn = nm.split()[0]
        if jn.startswith("J") and jn[1:].isdigit():
            side = "out" if nm.endswith("OutputShaft") else "fixed"
            side_vol[(jn, side)] = side_vol.get((jn, side), 0.0) + v
    link_density = {}
    for k in range(1, n):
        spec = os.path.join(ROOT, "links", f"LINK-{k}", f"LINK-{k}.txt")
        if os.path.isfile(spec):
            for p in lb.parse(spec)[0]:
                link_density[f"L{k} {p['name']}"] = p["density"]
    tool_vol = sum(v for (nm, *_), (v, _, _) in zip(bl, pr) if nm.startswith("tool-change"))
    for (nm, g, col, shp), (v, c, I) in zip(bl, pr):
        jn = nm.split()[0]
        if nm in link_density:
            rho = link_density[nm] * 1e-9                      # kg / mm^3
        elif jn.startswith("J") and jn[1:].isdigit():
            side = "out" if nm.endswith("OutputShaft") else "fixed"
            rho = side_mass[(jn, side)] / side_vol[(jn, side)]
        elif nm.startswith("ОПУ"):
            rho = ST * 1e-9
        elif nm.startswith("tool-change"):
            rho = iface / tool_vol
        else:                                                   # gripper: visual only, its mass is the payload
            tool_vis.append((nm, shp))
            continue
        add_mass(groups[g]["acc"], rho * v, c, rho * I)
        groups[g]["shapes"].append((nm, shp))
    # payload: block 80 x 80 x 2*payload_com along the flange axis, centre payload_com beyond the flange
    f = lay["flange"]
    pc = f["p"] + f["w"] * payload_com
    tool = {"shapes": tool_vis, "m": payload, "com": pc,
            "I": box_inertia(payload, 80, 80, 2 * payload_com) if payload else np.zeros((3, 3))}
    return groups, tool, notes


def origin_of(lay, g):
    """Link frame origin (world, mm, zero pose): base - world origin, link k - point of axis k."""
    return np.zeros(3) if g == 0 else np.array(lay["axes"][g - 1]["p"], float)


def mesh_tris(shapes, origin):
    T = []
    for _, shp in shapes:
        P, I = ra.mesh(shp)
        if len(I):
            T.append((P[I].astype(np.float64) - origin) * 1e-3)
    return np.concatenate(T) if T else np.zeros((0, 3, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    ap.add_argument("--program", default=os.path.join(ROOT, "robot", "RTC-7-demo.txt"))
    ap.add_argument("--out", default=os.path.join(ROOT, "sim", "RTC-7"))
    ap.add_argument("--payload", type=float, default=8.0, help="kg on the flange")
    ap.add_argument("--payload-com", type=float, default=100.0, help="mm beyond the flange")
    ap.add_argument("--iface", type=float, default=st.IFACE["mass"], help="kg, tool-change interface")
    a = ap.parse_args()
    lay = rs.read_layout(a.layout)
    rs.fk_poe(lay, np.zeros(len(lay["axes"])))           # fills lay["_Ts"] etc.
    prg = ra.read_program(a.program)
    tool_len = prg["tool"]
    groups, tool, notes = build(lay, a.payload, a.payload_com, a.iface, tool_len)
    os.makedirs(os.path.join(a.out, "meshes"), exist_ok=True)
    n = len(lay["axes"])
    lname = ["base_link"] + [f"link_{k}" for k in range(1, n + 1)]
    rows = []
    X = ['<?xml version="1.0"?>',
         f'<!-- RTC-7 - GENERATED by tools/urdf_export.py from {os.path.relpath(a.layout, ROOT)}, links/LINK-n,',
         '     joints/*; zero pose = the arm stretched up (as in the SolidWorks assembly). Units m, kg, kg*m^2. -->',
         '<robot name="RTC7">']
    for nm, c in RGB.items():
        X.append(f'  <material name="{nm}"><color rgba="{c[0]:.3f} {c[1]:.3f} {c[2]:.3f} 1"/></material>')

    def inertial(m, com, I):
        I = I * 1e-6                                          # kg*mm^2 -> kg*m^2
        return (f'    <inertial><origin xyz="{com[0] * 1e-3:.6f} {com[1] * 1e-3:.6f} {com[2] * 1e-3:.6f}" rpy="0 0 0"/>'
                f'<mass value="{m:.4f}"/>'
                f'<inertia ixx="{I[0, 0]:.6e}" ixy="{I[0, 1]:.6e}" ixz="{I[0, 2]:.6e}" '
                f'iyy="{I[1, 1]:.6e}" iyz="{I[1, 2]:.6e}" izz="{I[2, 2]:.6e}"/></inertial>')

    for g in range(n + 1):
        o = origin_of(lay, g)
        m, com, I = combine(groups[g]["acc"])
        tris = mesh_tris(groups[g]["shapes"], o)
        write_stl(os.path.join(a.out, "meshes", lname[g] + ".stl"), tris)
        mat = "opu" if g == 0 else "link"
        X.append(f'  <link name="{lname[g]}">')
        X.append(inertial(m, com - o, I))
        X.append(f'    <visual><origin xyz="0 0 0" rpy="0 0 0"/><geometry><mesh filename="meshes/{lname[g]}.stl" '
                 f'scale="1 1 1"/></geometry><material name="{mat}"/></visual>')
        X.append('  </link>')
        rows.append([lname[g], f"{m:.3f}", *[f"{v:.1f}" for v in com], *[f"{I[i, j] * 1e-6:.5f}" for i, j in
                     ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))], len(tris)])
        print(f"{lname[g]:10s} m {m:7.2f} kg  com {np.round(com, 1)} mm  triangles {len(tris)}")
    rated = []
    for i, ax in enumerate(lay["axes"]):
        jn = ax["joint"].rstrip("m")
        j = je.read_joint(os.path.join(ROOT, "joints", jn, jn + ".txt"))
        rd = st.card_data(os.path.join(ROOT, j["use"]["reducer"]))
        T = float(rd.get("T_design", rd["T_rated"]))
        rated.append((T, float(rd["T_startstop"]), rd.get("ratios", "?")))
        lo, hi = ra.LIMITS[i]
        p = origin_of(lay, i + 1) - origin_of(lay, i)
        w = np.array(ax["w"], float)
        X.append(f'  <joint name="{ax["name"]}" type="revolute">')
        X.append(f'    <!-- {ax["joint"]}; reducer rated torque {T:.0f} N*m (effort); velocity ASSUMED -->')
        X.append(f'    <parent link="{lname[i]}"/><child link="{lname[i + 1]}"/>')
        X.append(f'    <origin xyz="{p[0] * 1e-3:.6f} {p[1] * 1e-3:.6f} {p[2] * 1e-3:.6f}" rpy="0 0 0"/>')
        X.append(f'    <axis xyz="{w[0]:.0f} {w[1]:.0f} {w[2]:.0f}"/>')
        X.append(f'    <limit lower="{math.radians(lo):.5f}" upper="{math.radians(hi):.5f}" effort="{T:.0f}" velocity="3.14"/>')
        X.append('  </joint>')
    # tool body (fixed to link_7): gripper visual + payload
    o7 = origin_of(lay, n)
    tris = mesh_tris(tool["shapes"], o7)
    write_stl(os.path.join(a.out, "meshes", "tool.stl"), tris)
    X.append('  <link name="tool">')
    if tool["m"] > 0:
        X.append(inertial(tool["m"], tool["com"] - o7, tool["I"]))
    X.append('    <visual><origin xyz="0 0 0" rpy="0 0 0"/><geometry><mesh filename="meshes/tool.stl" scale="1 1 1"/>'
             '</geometry><material name="tool"/></visual>')
    X.append('  </link>')
    X.append('  <joint name="tool_fixed" type="fixed"><parent link="link_7"/><child link="tool"/>'
             '<origin xyz="0 0 0" rpy="0 0 0"/></joint>')
    f = lay["flange"]
    tcp = f["p"] + f["w"] * tool_len - o7
    X.append('  <link name="tcp"/>')
    X.append(f'  <joint name="tcp_fixed" type="fixed"><parent link="tool"/><child link="tcp"/>'
             f'<origin xyz="{tcp[0] * 1e-3:.6f} {tcp[1] * 1e-3:.6f} {tcp[2] * 1e-3:.6f}" rpy="0 0 0"/></joint>')
    X.append('</robot>')
    upath = os.path.join(a.out, "RTC-7.urdf")
    open(upath, "w", encoding="utf-8").write("\n".join(X) + "\n")
    rows.append(["tool (payload)", f"{tool['m']:.3f}", *[f"{v:.1f}" for v in tool["com"]],
                 *[f"{v * 1e-6:.5f}" for v in (tool["I"][0, 0], tool["I"][1, 1], tool["I"][2, 2], 0, 0, 0)], len(tris)])
    with open(os.path.join(a.out, "RTC-7-bodies.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["link", "mass_kg", "com_x_mm", "com_y_mm", "com_z_mm", "Ixx", "Iyy", "Izz", "Ixy", "Ixz",
                    "Iyz", "triangles"])
        w.writerows(rows)
    # demo trajectory
    frames, _ = ra.trajectory(lay, prg)
    with open(os.path.join(a.out, "RTC-7-demo-traj.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s"] + [ax["name"] + "_rad" for ax in lay["axes"]])
        for k, q in enumerate(frames):
            w.writerow([f"{k / prg['fps']:.5f}"] + [f"{v:.6f}" for v in q])
    with open(os.path.join(a.out, "RTC-7-rated.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["joint", "drive", "T_rated_Nm", "T_startstop_Nm"])
        for ax, (T, Tss, _) in zip(lay["axes"], rated):
            w.writerow([ax["name"], ax["joint"], f"{T:.0f}", f"{Tss:.0f}"])
    for s in notes:
        print("note:", s)
    print(f"URDF -> {upath}; trajectory {len(frames)} frames at {prg['fps']} fps")


if __name__ == "__main__":
    main()
