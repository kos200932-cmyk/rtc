#!/usr/bin/env python3
"""Split the STEP of a frameless motor into rotor and stator, moved into the card frame.

    python tools/step_split.py components/T-motor/RI80-V2-KV75/RI80-V2-KV75.txt

Reads STEP and FRAME (axis=+X|-X|+Y|-Y|+Z|-Z origin=x,y,z) and PORT rotor (id=, od=) from the
card. Every solid of the STEP is classified: the rotor is the solid whose coaxial cylinders
include the rotor bore (id) and the rotor OD (od); all other solids are the stator (with the
sensor board, leads...). Both are moved so that the card axis is +X and the card origin is 0,
the same turn as the macro uses (axis Z -> rotation +90 deg about Y, Y -> -90 deg about Z), and
written as <STEP name>-rotor.step / -stator.step next to the card. Add to the card:
    BODY rotor  <name>-rotor.step
    BODY stator <name>-stator.step
Needs: pip install cadquery-ocp
"""
import math
import os
import re
import sys

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRep import BRep_Builder
from OCP.Bnd import Bnd_Box
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec


def card_info(path):
    info = {"axis": "+X", "origin": (0.0, 0.0, 0.0)}
    for raw in open(path, encoding="utf-8"):
        t = re.split(r"[#;]", raw, maxsplit=1)[0].split()
        if not t:
            continue
        if t[0] == "STEP":
            info["step"] = t[1]
        elif t[0] == "FRAME":
            for kv in t[1:]:
                k, _, v = kv.partition("=")
                if k == "axis":
                    info["axis"] = v.upper()
                elif k == "origin":
                    info["origin"] = tuple(float(x) for x in v.split(","))
        elif t[0] == "PORT" and t[1] == "rotor":
            kv = dict(x.split("=", 1) for x in t[4:] if "=" in x)
            info["rotor_id"], info["rotor_od"] = float(kv["id"]), float(kv["od"])
    return info


def solids(shape):
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        yield TopoDS.Solid(ex.Current())
        ex.Next()


def coaxial_diameters(solid, axis_vec, axis_pnt):
    out = set()
    ex = TopExp_Explorer(solid, TopAbs_FACE)
    while ex.More():
        ad = BRepAdaptor_Surface(TopoDS.Face(ex.Current()))
        if ad.GetType() == GeomAbs_Cylinder:
            c = ad.Cylinder()
            d = c.Axis().Direction()
            if abs(abs(d.X() * axis_vec[0] + d.Y() * axis_vec[1] + d.Z() * axis_vec[2]) - 1) < 1e-4:
                p = c.Axis().Location()
                v = (p.X() - axis_pnt[0], p.Y() - axis_pnt[1], p.Z() - axis_pnt[2])
                along = sum(a * b for a, b in zip(v, axis_vec))
                off = math.sqrt(max(0.0, sum(a * a for a in v) - along * along))
                if off < 1e-3:
                    out.add(round(2 * c.Radius(), 2))
        ex.Next()
    return out


def frame_trsf(axis, origin):
    t1 = gp_Trsf()
    t1.SetTranslation(gp_Vec(-origin[0], -origin[1], -origin[2]))
    sg = -1 if axis.startswith("-") else 1
    r = gp_Trsf()
    o = gp_Pnt(0, 0, 0)
    if axis[-1] == "X":
        if sg < 0:
            r.SetRotation(gp_Ax1(o, gp_Dir(0, 1, 0)), math.pi)
    elif axis[-1] == "Y":
        r.SetRotation(gp_Ax1(o, gp_Dir(0, 0, 1)), -sg * math.pi / 2)
    elif axis[-1] == "Z":
        r.SetRotation(gp_Ax1(o, gp_Dir(0, 1, 0)), sg * math.pi / 2)
    return r.Multiplied(t1)


def bbox(shape):
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    lo, hi = b.CornerMin(), b.CornerMax()
    return (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z())


def write(shape, path):
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    w = STEPControl_Writer()
    w.Transfer(shape, STEPControl_AsIs)
    if w.Write(path) != IFSelect_RetDone:
        sys.exit(f"cannot write {path}")


def main():
    card = sys.argv[1]
    folder = os.path.dirname(card)
    info = card_info(card)
    rd = STEPControl_Reader()
    if rd.ReadFile(os.path.join(folder, info["step"])) != IFSelect_RetDone:
        sys.exit("cannot read the STEP")
    rd.TransferRoots()
    shape = rd.OneShape()
    ax = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[info["axis"][-1]]
    trsf = frame_trsf(info["axis"], info["origin"])

    builder = BRep_Builder()
    parts = {"rotor": TopoDS_Compound(), "stator": TopoDS_Compound()}
    for c in parts.values():
        builder.MakeCompound(c)
    counts = {"rotor": 0, "stator": 0}
    for s in solids(shape):
        ds = coaxial_diameters(s, ax, info["origin"])
        kind = "rotor" if (info["rotor_id"] in ds and round(info["rotor_od"], 2) in ds) else "stator"
        moved = BRepBuilderAPI_Transform(s, trsf, True).Shape()
        builder.Add(parts[kind], moved)
        counts[kind] += 1
    if counts["rotor"] != 1:
        sys.exit(f"expected exactly one rotor solid, found {counts['rotor']}")
    base = os.path.splitext(info["step"])[0]
    for kind, comp in parts.items():
        out = os.path.join(folder, f"{base}-{kind}.step")
        write(comp, out)
        b = bbox(comp)
        print(f"{kind}: {counts[kind]} solid(s) -> {out}; x {b[0]:.2f}..{b[3]:.2f}, "
              f"y {b[1]:.2f}..{b[4]:.2f}, z {b[2]:.2f}..{b[5]:.2f}")


if __name__ == "__main__":
    main()
