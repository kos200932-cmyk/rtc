"""STEP model of the 6-axis force / torque sensor Kunwei KWR90 (user drawing 2026-11-12) -> components/Kunwei/KWR90/.

Frame of the drawing: Z - the sensor axis, z = 0 - the mounting side (to the robot, J7), z = 24 - the tool side (to the
SZU); X+, Y+ as in the "Tool Side" view (seen from the tool side).
From the drawing:
  body D90 x 23, tool-side boss D48 x 1 (overall height 24 +-0.05), hollow D30 through;
  tool side: 6 x M5 depth 10 on PCD40 (EQS, at 30 + 60k deg), 2 x pin D5 +0.02 depth 6 on PCD40 at 0 / 180 deg;
             6 counterbored through holes D5.5 / D9 on PCD78 (0 + 60k deg; section A-A: D9 x 6, D5.5 x 14 - modelled
             D9 x 6 from the tool face, D5.5 through) - the bolts that fix the sensor to the mounting side;
  mounting side: bolt circle PCD78 +-0.05 (the same 6 holes), 2 x pin D5 +0.02 depth 6, cable outlet hole.
Cable outlet boss (user photos 2026-11-12, not dimensioned - sized from the photos against D90 / h 26): a block on the
side of the body at -Y (between the two lower counterbored holes, as seen from the tool side), flush with the
mounting face: 18 wide x 12 high (z 0..12), 8 proud of D90, edges R1; a clamp plate with 4 x M2 on its outer face; the
cable D3 leaves it tangentially to +X (stub 25 mm in the model, a separate body).
Not dimensioned on the drawing, assumed: the mounting-side pins on PCD78 at 26 / 206 deg, the outlet hole D4 at r 30
(148 deg), the shallow relief / small holes of the faces are left out. Material: aluminium alloy (mass 0.34 kg).
"""
import os, sys, math
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

H_BODY, H_BOSS, D_BODY, D_BOSS, D_BORE = 23.0, 1.0, 90.0, 48.0, 30.0
H = H_BODY + H_BOSS

def cyl(x, y, z, d, h, down=False):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, -1 if down else 1)), d / 2, h).Shape()

def polar(pcd, deg):
    a = math.radians(deg); return pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)

BOSS_W, BOSS_H, BOSS_OUT = 18.0, 12.0, 8.0      # cable boss: width (X), height (Z), proud of D90 (radial)

def xcyl(x, y, z, d, h):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(1, 0, 0)), d / 2, h).Shape()

def ycyl(x, y, z, d, h):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, -1, 0)), d / 2, h).Shape()

def cable_boss():
    y_out = -(D_BODY / 2 + BOSS_OUT); y_in = -(D_BODY / 2 - 6)          # 6 mm into the body - fused with it
    b = BRepPrimAPI_MakeBox(gp_Pnt(-BOSS_W / 2, y_out, 0), BOSS_W, y_in - y_out, BOSS_H).Shape()
    f = BRepFilletAPI_MakeFillet(b); e = TopExp_Explorer(b, TopAbs_EDGE)
    while e.More(): f.Add(1.0, TopoDS.Edge(e.Current())); e.Next()
    try: b = f.Shape()
    except Exception: pass
    return b, y_out

def build():
    s = BRepAlgoAPI_Fuse(cyl(0, 0, 0, D_BODY, H_BODY), cyl(0, 0, H_BODY - 0.01, D_BOSS, H_BOSS + 0.01)).Shape()
    boss, y_out = cable_boss(); s = BRepAlgoAPI_Fuse(s, boss).Shape()
    cuts = [cyl(0, 0, -1, D_BORE, H + 2)]
    for k in range(6):                                   # tool side: 6 x M5 x 10 (tap drill D4.2) on PCD40
        x, y = polar(40, 30 + 60 * k); cuts.append(cyl(x, y, H + 0.01, 4.2, 10.01, down=True))
    for deg in (0, 180):                                 # tool side: 2 x pin D5 x 6 on PCD40
        x, y = polar(40, deg); cuts.append(cyl(x, y, H + 0.01, 5.0, 6.01, down=True))
    for k in range(6):                                   # 6 counterbored through holes on PCD78
        x, y = polar(78, 60 * k)
        cuts.append(cyl(x, y, -1, 5.5, H_BODY + 2)); cuts.append(cyl(x, y, H_BODY + 0.01, 9.0, 6.01, down=True))
    for deg in (26, 206):                                # mounting side: 2 x pin D5 x 6 (position assumed)
        x, y = polar(78, deg); cuts.append(cyl(x, y, -0.01, 5.0, 6.01))
    x, y = polar(60, 148); cuts.append(cyl(x, y, -0.01, 4.0, 8.0))   # cable outlet (assumed)
    yc = y_out + 4.0; zc = BOSS_H / 2                                  # cable bore along +X, out of the right side
    cuts.append(xcyl(-2.0, yc, zc, 3.4, BOSS_W / 2 + 3.0))
    for dx in (-5.5, 5.5):                                              # clamp plate: 4 x M2 on the outer face
        for dz in (-3.5, 3.5): cuts.append(ycyl(dx, y_out + 0.01, zc + dz, 1.6, 5.0))
    for c in cuts: s = BRepAlgoAPI_Cut(s, c).Shape()
    return s

def cable(length=25.0):
    _, y_out = cable_boss()
    return xcyl(-2.0, y_out + 4.0, BOSS_H / 2, 3.0, BOSS_W / 2 + 2.0 + length)

if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "components", "Kunwei", "KWR90"); os.makedirs(out, exist_ok=True)
    s = build(); g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g); v = g.Mass()
    comp = TopoDS_Compound(); bb = BRep_Builder(); bb.MakeCompound(comp); bb.Add(comp, s); bb.Add(comp, cable())
    w = STEPControl_Writer(); w.Transfer(comp, STEPControl_AsIs); w.Write(os.path.join(out, "KWR90.STEP"))
    print(f"KWR90.STEP: volume {v / 1e3:.1f} cm3, mass {v * 2.7e-6:.3f} kg as aluminium (catalogue 0.34 kg)")
