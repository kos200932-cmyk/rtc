#!/usr/bin/env python3
"""Build the parts of a link spec (prismatic parts: PRISM / CUT / TAP ...) with OpenCascade.

    python tools/link_build.py links/LINK-1/LINK-1.txt [--layout robot/RTC-7-layout.txt]
                               [--png out.png] [--step] [--no-check]

The same spec is built in SolidWorks by macros/BuildFromSpec.bas (feature tree); this script gives
the STEP of every part (--step, next to the spec), volume / mass, a picture with the neighbouring
joint envelopes, and an interference check against the joint envelopes (zero pose) and the fixed
ОПУ outer ring.

Prismatic part lines (inside PART ... END), coordinates = robot world frame at the zero pose, mm:
  PRISM <X|Y|Z> <a0> <a1> <shape>     add material: <shape> in the plane normal to the axis at
                                     level a0, extruded to level a1
  CUT   <X|Y|Z> <a0> <a1> <shape>     remove material, same geometry
  TAP   <X|Y|Z> <a0> <a1> <uc> <vc> <n> <pcd> <M..> <ang>   tapped holes (tap drill cut, thread noted)
  shapes, in the plane coordinates (u, v): X -> (y, z), Y -> (x, z), Z -> (x, y):
    RECT u0 u1 v0 v1  |  CIRC uc vc D  |  RING uc vc D d  |  POLY u1 v1 u2 v2 ...
    PATTERN uc vc n pcd d ang          (n circles D=d on the pitch circle, first at ang deg from +u to +v)
  DENSITY <kg/m3>                     material density (mass = volume x density)
  PORTP <name> <X|Y|Z> <level> <dir> [key=value ...]   interface plane PORT_<name>
"""
import argparse
import math
import os
import re
import sys

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire)
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAP = {"M3": 2.5, "M4": 3.3, "M5": 4.2, "M6": 5.0, "M8": 6.8, "M10": 8.5, "M12": 10.2, "M16": 14.0}
AX = {"X": 0, "Y": 1, "Z": 2}
UV = {"X": (1, 2), "Y": (0, 2), "Z": (0, 1)}


def num(s):
    return float(s.replace(",", "."))


def parse(path):
    parts, cur, data = [], None, {}
    for raw in open(path, encoding="utf-8-sig"):
        t = re.split(r"[#;]", raw, maxsplit=1)[0].split()
        if not t:
            continue
        k = t[0].upper()
        if k == "PART":
            cur = {"name": t[1], "ops": [], "ports": [], "density": 2700.0, "motion": "fixed", "color": None}
            parts.append(cur)
        elif k == "END":
            cur = None
        elif k == "DATA":
            data.update(kv.split("=", 1) for kv in t[1:] if "=" in kv)
        elif cur is None:
            continue
        elif k in ("PRISM", "CUT"):
            cur["ops"].append((k, t[1].upper(), num(t[2]), num(t[3]), t[4].upper(), [num(v) for v in t[5:]]))
        elif k == "TAP":
            uc, vc, n, pcd, size, ang = num(t[4]), num(t[5]), int(num(t[6])), num(t[7]), t[8].upper(), num(t[9])
            cur["ops"].append(("CUT", t[1].upper(), num(t[2]), num(t[3]), "PATTERN",
                               [uc, vc, n, pcd, TAP[size], ang]))
        elif k == "DENSITY":
            cur["density"] = num(t[1])
        elif k == "MOTION":
            cur["motion"] = t[1].lower()
        elif k == "COLOR":
            cur["color"] = tuple(int(num(v)) for v in t[1:4])
        elif k == "PORTP":
            cur["ports"].append({"name": t[1], "axis": t[2].upper(), "level": num(t[3]), "dir": num(t[4]),
                                 "info": " ".join(t[5:])})
    return parts, data


def pnt(axis, level, u, v):
    c = [0.0, 0.0, 0.0]
    c[AX[axis]] = level
    iu, iv = UV[axis]
    c[iu], c[iv] = u, v
    return gp_Pnt(*c)


def circle_wire(axis, level, uc, vc, d):
    n = [0.0, 0.0, 0.0]
    n[AX[axis]] = 1.0
    circ = gp_Circ(gp_Ax2(pnt(axis, level, uc, vc), gp_Dir(*n)), d / 2)
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circ).Edge()).Wire()


def poly_wire(axis, level, uv):
    mp = BRepBuilderAPI_MakePolygon()
    for u, v in uv:
        mp.Add(pnt(axis, level, u, v))
    mp.Close()
    return mp.Wire()


def faces(axis, level, shape, a):
    """List of planar faces for a shape."""
    if shape == "RECT":
        u0, u1, v0, v1 = a
        return [BRepBuilderAPI_MakeFace(poly_wire(axis, level, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])).Face()]
    if shape == "POLY":
        uv = list(zip(a[0::2], a[1::2]))
        return [BRepBuilderAPI_MakeFace(poly_wire(axis, level, uv)).Face()]
    if shape == "CIRC":
        return [BRepBuilderAPI_MakeFace(circle_wire(axis, level, a[0], a[1], a[2])).Face()]
    if shape == "RING":
        mf = BRepBuilderAPI_MakeFace(circle_wire(axis, level, a[0], a[1], a[2]))
        inner = circle_wire(axis, level, a[0], a[1], a[3])
        inner.Reverse()
        mf.Add(inner)
        return [mf.Face()]
    if shape == "PATTERN":
        uc, vc, n, pcd, d, ang = a
        out = []
        for k in range(int(n)):
            t = math.radians(ang + k * 360.0 / n)
            out.append(BRepBuilderAPI_MakeFace(circle_wire(axis, level, uc + pcd / 2 * math.cos(t),
                                                           vc + pcd / 2 * math.sin(t), d)).Face())
        return out
    raise ValueError(f"unknown shape {shape}")


def prism(axis, a0, a1, shape, a):
    v = [0.0, 0.0, 0.0]
    v[AX[axis]] = a1 - a0
    res = None
    for f in faces(axis, a0, shape, a):
        s = BRepPrimAPI_MakePrism(f, gp_Vec(*v)).Shape()
        res = s if res is None else BRepAlgoAPI_Fuse(res, s).Shape()
    return res


def build_part(p):
    shape = None
    for op, axis, a0, a1, sh, a in p["ops"]:
        s = prism(axis, a0, a1, sh, a)
        if op == "PRISM":
            shape = s if shape is None else BRepAlgoAPI_Fuse(shape, s).Shape()
        elif shape is not None:
            shape = BRepAlgoAPI_Cut(shape, s).Shape()
    return shape


def volume(shape):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    return g.Mass(), g.CentreOfMass()


def write_step(shape, path):
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    w = STEPControl_Writer()
    w.Transfer(shape, STEPControl_AsIs)
    if w.Write(path) != IFSelect_RetDone:
        raise RuntimeError(f"cannot write {path}")


def triangles(shape, defl=0.6):
    BRepMesh_IncrementalMesh(shape, defl, False, 0.4, True)
    tris = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current())
        loc = TopLoc_Location()
        tr = BRep_Tool.Triangulation_s(f, loc)
        if tr is not None:
            T = loc.Transformation()
            P = [tr.Node(i).Transformed(T) for i in range(1, tr.NbNodes() + 1)]
            P = np.array([[q.X(), q.Y(), q.Z()] for q in P])
            for i in range(1, tr.NbTriangles() + 1):
                a, b, c = tr.Triangle(i).Get()
                tris.append(P[[a - 1, b - 1, c - 1]])
        ex.Next()
    return tris


def revolved(origin, u, pts):
    """Solid of revolution of a profile (x along u, r) about the line (origin, u)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1
    u = np.asarray(u, float)
    e = np.cross(u, [1, 0, 0] if abs(u[0]) < 0.9 else [0, 1, 0])
    e /= np.linalg.norm(e)
    mp = BRepBuilderAPI_MakePolygon()
    for x, r in pts:
        q = origin + u * x + e * r
        mp.Add(gp_Pnt(*q))
    mp.Close()
    f = BRepBuilderAPI_MakeFace(mp.Wire()).Face()
    return BRepPrimAPI_MakeRevol(f, gp_Ax1(gp_Pnt(*origin), gp_Dir(*u)), 2 * math.pi).Shape()


def envelope_solids(lay_path, joints):
    """Joints at the zero pose as revolved solids of their real part profiles (+ motor and sensor-cover
    envelopes) and the fixed ОПУ outer ring."""
    import joint_envelope as je
    import robot_scheme as rs
    lay = rs.read_layout(lay_path)
    env = je.all_joints()
    out = []
    for a in lay["axes"]:
        if a.get("face") is None or (joints and a["name"] not in joints):
            continue
        e = env.get(a["joint"]) or env.get(a["joint"].rstrip("m"))
        md = np.zeros(3)
        md["XYZ".index(a["motor"][1])] = 1 if a["motor"][0] == "+" else -1
        u = -md
        origin = a["face"] - u * e["x_out"]
        for nm, kind, pts in e["profiles"]:
            out.append((f"{a['name']} {nm}", revolved(origin, u, pts), a["name"], kind))
        if a["joint"].endswith("m"):
            for nm, r0, r1, kind in (("ОПУ inner ring", 57.5, 88.5, "rot"),):
                out.append((f"{a['name']} {nm}", revolved(np.array([0, 0, -28.0]), np.array([0, 0, 1.0]),
                                                           [(0, r0), (28, r0), (28, r1), (0, r1)]), a["name"], kind))
    out.append(("ОПУ outer ring (fixed)", revolved(np.array([0, 0, -28.0]), np.array([0, 0, 1.0]),
                                                    [(0, 89.5), (28, 89.5), (28, 120), (0, 120)]), "base", "fixed"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--layout", default=os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    ap.add_argument("--joints", default="", help="joints to show / check, e.g. J1,J2 (default: all)")
    ap.add_argument("--png")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--gap", type=float, default=0.0, help="report envelopes closer than this (mm) - not used yet")
    a = ap.parse_args()
    parts, data = parse(a.spec)
    folder = os.path.dirname(os.path.abspath(a.spec))
    built = []
    print(f"{'part':<28} {'volume cm3':>10} {'mass kg':>8}   centre of mass, mm")
    for p in parts:
        s = build_part(p)
        v, cg = volume(s)
        m = v * 1e-9 * p["density"]
        built.append((p, s, m))
        print(f"{p['name']:<28} {v / 1000:>10.1f} {m:>8.2f}   {cg.X():.0f} {cg.Y():.0f} {cg.Z():.0f}")
        if a.step:
            write_step(s, os.path.join(folder, p["name"] + ".step"))
    print(f"{'total':<28} {'':>10} {sum(b[2] for b in built):>8.2f}")

    joints = [j.strip() for j in a.joints.split(",") if j.strip()]
    env = envelope_solids(a.layout, joints)
    bad = 0
    for p, s, m in built:
        for nm, sol, jn, kind in env:
            v, _ = volume(BRepAlgoAPI_Common(s, sol).Shape())
            if v > 1.0:
                bad += 1
                print(f"INTERFERENCE {p['name']} x {nm}: {v:.0f} mm3")
    print("interference check:", "OK" if not bad else f"{bad} overlap(s)")

    if a.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        cols = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
        fig = plt.figure(figsize=(16, 8))
        views = [(25, -60, "isometric"), (0, -90, "front (along +Y)"), (90, -90, "top (along -Z)")]
        allp = []
        meshes = [(p["name"], triangles(s), cols[k % len(cols)]) for k, (p, s, m) in enumerate(built)]
        envm = [(nm, triangles(sol, 1.5)) for nm, sol, jn, kind in env]
        for vi, (el, az, title) in enumerate(views):
            ax = fig.add_subplot(1, 3, vi + 1, projection="3d")
            for nm, tri in envm:
                ax.add_collection3d(Poly3DCollection(tri, facecolor="0.75", edgecolor="none", alpha=0.18))
            from matplotlib.colors import to_rgb
            light = np.array([0.4, -0.6, 0.7])
            light /= np.linalg.norm(light)
            for nm, tri, c in meshes:
                T = np.array(tri)
                nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
                nrm /= np.linalg.norm(nrm, axis=1)[:, None] + 1e-12
                shade = 0.45 + 0.55 * np.abs(nrm @ light)
                fc = np.clip(np.array(to_rgb(c))[None, :] * shade[:, None], 0, 1)
                ax.add_collection3d(Poly3DCollection(tri, facecolors=fc, edgecolor="none"))
                allp.append(np.concatenate(tri))
            P = np.concatenate(allp)
            lo, hi = P.min(0) - 40, P.max(0) + 40
            ctr, half = (lo + hi) / 2, (hi - lo).max() / 2
            ax.set_xlim(ctr[0] - half, ctr[0] + half)
            ax.set_ylim(ctr[1] - half, ctr[1] + half)
            ax.set_zlim(ctr[2] - half, ctr[2] + half)
            ax.set_box_aspect((1, 1, 1))
            ax.view_init(elev=el, azim=az)
            ax.set_title(title, fontsize=10)
            ax.set_xlabel("X"), ax.set_ylabel("Y"), ax.set_zlabel("Z")
            ax.tick_params(labelsize=7)
        handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in meshes]
        fig.legend(handles + [plt.Rectangle((0, 0), 1, 1, color="0.75", alpha=0.4)],
                   [n for n, _, _ in meshes] + ["joint envelopes, ОПУ"], loc="lower center", ncol=6, fontsize=9,
                   frameon=False)
        fig.suptitle(os.path.basename(a.spec) + " - zero pose", fontsize=11)
        fig.tight_layout(rect=(0, 0.05, 1, 0.97))
        fig.savefig(a.png, dpi=110)
        print("picture ->", a.png)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
