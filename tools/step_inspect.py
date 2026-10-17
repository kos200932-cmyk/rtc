#!/usr/bin/env python3
"""Inspect a STEP model of a rotational component (motor, sensor, bearing...).

    python tools/step_inspect.py model.step [--json out.json] [--png section.png]

Needs OpenCascade for Python:  pip install cadquery-ocp

Prints, for every solid: volume, bounding box, and - relative to the common axis found
from the cylindrical faces - the coaxial cylinders (diameter, axial span, inner/outer),
the planar end faces (axial position, radial span) and the off-axis hole groups (count,
pitch circle, diameter). This is what is needed to write PORT lines of a component card.
"""
import argparse
import json
import math
import sys
from collections import defaultdict

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS


def load(path):
    r = STEPControl_Reader()
    if r.ReadFile(path) != IFSelect_RetDone:
        sys.exit(f"cannot read {path}")
    r.TransferRoots()
    return r.OneShape()


def items(shape, kind, cast):
    ex = TopExp_Explorer(shape, kind)
    while ex.More():
        yield cast(ex.Current())
        ex.Next()


def vec(p):
    return (p.X(), p.Y(), p.Z())


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    return tuple(x / n for x in a)


def face_vertices(face):
    return [vec(BRep_Tool.Pnt_s(TopoDS.Vertex(v))) for v in items(face, TopAbs_VERTEX, lambda s: s)]


def face_area(face):
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, g)
    return g.Mass()


def analyse(shape):
    solids = list(items(shape, TopAbs_SOLID, TopoDS.Solid))
    # --- common axis: direction shared by the largest-area cylinders
    cyl = []
    for si, s in enumerate(solids):
        for f in items(s, TopAbs_FACE, TopoDS.Face):
            ad = BRepAdaptor_Surface(f)
            if ad.GetType() == GeomAbs_Cylinder:
                c = ad.Cylinder()
                ax = c.Axis()
                cyl.append((si, f, vec(ax.Location()), unit(vec(ax.Direction())), c.Radius(), face_area(f)))
    if not cyl:
        sys.exit("no cylindrical faces")
    votes = defaultdict(float)
    for _, _, _, d, _, a in cyl:
        key = tuple(round(abs(x), 3) for x in d)
        votes[key] += a
    axis_dir = unit(max(votes, key=votes.get))
    # axis location: area-weighted mean of the locations of coaxial-direction cylinders, projected
    big = [c for c in cyl if abs(abs(dot(c[3], axis_dir)) - 1) < 1e-3]
    big.sort(key=lambda c: -c[5])
    loc = big[0][2]
    loc = sub(loc, tuple(dot(loc, axis_dir) * x for x in axis_dir))   # point of the axis closest to origin

    def to_axis(p):
        v = sub(p, loc)
        x = dot(v, axis_dir)
        rvec = sub(v, tuple(x * k for k in axis_dir))
        return x, norm(rvec), rvec

    # reference directions in the plane normal to the axis
    ref = (1, 0, 0) if abs(axis_dir[0]) < 0.9 else (0, 1, 0)
    e1 = unit(cross(axis_dir, ref))
    e2 = cross(axis_dir, e1)

    out = {"axis_dir": axis_dir, "axis_point": loc, "e1": e1, "e2": e2, "solids": []}
    for si, s in enumerate(solids):
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(s, g)
        cg = vec(g.CentreOfMass())
        bb = Bnd_Box()
        BRepBndLib.Add_s(s, bb)
        cmin, cmax = bb.CornerMin(), bb.CornerMax()
        xmin, ymin, zmin, xmax, ymax, zmax = cmin.X(), cmin.Y(), cmin.Z(), cmax.X(), cmax.Y(), cmax.Z()
        info = {"index": si, "volume_cm3": g.Mass() / 1000, "centroid_axial": to_axis(cg)[0],
                "centroid_offset": to_axis(cg)[1],
                "bbox": [xmin, ymin, zmin, xmax, ymax, zmax], "coaxial": [], "planes": [], "holes": []}
        xs_all = []
        hole_raw = []
        for f in items(s, TopAbs_FACE, TopoDS.Face):
            ad = BRepAdaptor_Surface(f)
            vs = face_vertices(f)
            ax_pos = [to_axis(p)[0] for p in vs] or [0]
            xs_all += ax_pos
            if ad.GetType() == GeomAbs_Cylinder:
                c = ad.Cylinder()
                d = unit(vec(c.Axis().Direction()))
                if abs(abs(dot(d, axis_dir)) - 1) > 1e-3:
                    continue
                x0, rr, _ = to_axis(vec(c.Axis().Location()))
                # outward normal points away from the axis -> outer surface of material
                u = (ad.FirstUParameter() + ad.LastUParameter()) / 2
                v = (ad.FirstVParameter() + ad.LastVParameter()) / 2
                from OCP.gp import gp_Pnt, gp_Vec
                p, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
                ad.D1(u, v, p, du, dv)
                n = du.Crossed(dv)
                if f.Orientation() == TopAbs_REVERSED:
                    n.Reverse()
                pa = to_axis(vec(p))
                radial_out = dot(vec(n), pa[2]) > 0 if pa[1] > 1e-9 else True
                span = (min(ax_pos), max(ax_pos))
                sweep = math.degrees(ad.LastUParameter() - ad.FirstUParameter())
                if rr < 1e-3:   # coaxial with the main axis
                    info["coaxial"].append({"d": round(2 * c.Radius(), 3), "x0": round(span[0], 3),
                                            "x1": round(span[1], 3), "outer": radial_out,
                                            "sweep_deg": round(sweep, 1)})
                else:           # parallel off-axis cylinder: hole (inner) or pin (outer)
                    _, _, rv = to_axis(vec(c.Axis().Location()))
                    ang = math.degrees(math.atan2(dot(rv, e2), dot(rv, e1)))
                    hole_raw.append((round(2 * rr, 2), round(2 * c.Radius(), 2), round(ang, 1),
                                     round(span[0], 2), round(span[1], 2), radial_out))
            elif ad.GetType() == GeomAbs_Plane:
                pl = ad.Plane()
                d = unit(vec(pl.Axis().Direction()))
                if abs(abs(dot(d, axis_dir)) - 1) > 1e-3:
                    continue
                rs = [to_axis(p)[1] for p in vs]
                info["planes"].append({"x": round(ax_pos[0], 3), "r_min": round(min(rs), 2) if rs else None,
                                       "r_max": round(max(rs), 2) if rs else None, "area": round(face_area(f), 1)})
        info["axial_span"] = [round(min(xs_all), 3), round(max(xs_all), 3)]
        # coaxial: merge duplicates (split faces)
        merged = {}
        for c in info["coaxial"]:
            k = (c["d"], c["outer"])
            m = merged.setdefault(k, dict(c))
            m["x0"], m["x1"] = min(m["x0"], c["x0"]), max(m["x1"], c["x1"])
        info["coaxial"] = sorted(merged.values(), key=lambda c: (c["d"], c["x0"]))
        merged = {}
        for pnl in info["planes"]:
            k = pnl["x"]
            m = merged.setdefault(k, dict(pnl))
            m["r_min"] = min(m["r_min"], pnl["r_min"])
            m["r_max"] = max(m["r_max"], pnl["r_max"])
            m["area"] = round(m["area"] + pnl["area"] if m is not pnl else m["area"], 1)
        info["planes"] = sorted(merged.values(), key=lambda p: p["x"])
        # holes: group by (pcd, d, inner/outer); several faces of one hole -> unique angles
        groups = defaultdict(dict)
        for pcd, dd, ang, x0, x1, outer in hole_raw:
            key = (pcd, dd, "pin" if outer else "hole")
            a = round(ang) % 360
            g_ = groups[key].setdefault(a, [x0, x1])
            g_[0], g_[1] = min(g_[0], x0), max(g_[1], x1)
        for (pcd, dd, kind), angs in sorted(groups.items()):
            spans = list(angs.values())
            info["holes"].append({"kind": kind, "pcd": pcd, "d": dd, "n": len(angs),
                                  "angles": sorted(angs), "x0": min(s_[0] for s_ in spans),
                                  "x1": max(s_[1] for s_ in spans)})
        out["solids"].append(info)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--json")
    a = ap.parse_args()
    shape = load(a.step)
    res = analyse(shape)
    print(f"axis direction {tuple(round(x, 4) for x in res['axis_dir'])}, "
          f"axis point {tuple(round(x, 3) for x in res['axis_point'])}; e1 {tuple(round(x, 3) for x in res['e1'])}")
    for s in res["solids"]:
        print(f"\n== solid {s['index']}: volume {s['volume_cm3']:.2f} cm3, axial span {s['axial_span']}, "
              f"centroid x={s['centroid_axial']:.2f} (off-axis {s['centroid_offset']:.3f})")
        for c in s["coaxial"]:
            print(f"   cyl D{c['d']:<8} x {c['x0']:>8} .. {c['x1']:<8} {'OUTER' if c['outer'] else 'inner'}"
                  f"  sweep {c['sweep_deg']}")
        for p in s["planes"]:
            print(f"   face x={p['x']:<8} r {p['r_min']} .. {p['r_max']}")
        for h in s["holes"]:
            print(f"   {h['kind']}s {h['n']} x D{h['d']} on PCD {h['pcd']}, x {h['x0']}..{h['x1']}, "
                  f"angles {h['angles'][:12]}{' ...' if len(h['angles']) > 12 else ''}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
