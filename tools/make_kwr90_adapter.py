"""Adapter J7 output (DMRD-KB17) -> 6-axis F/T sensor Kunwei KWR90 (user 2026-11-12), with a side-wall window that takes
the sensor cable into the centre of the joint.

Frame: Z - the J7 axis, z = 0 - the adapter bottom (J7 side) = joint x 47.5 (1 mm from the reducer housing face x 46.5),
z = H - the top face, on it the sensor mounting face (sensor z = 0).
J7 output (DMRD-KB17-03_OutputShaft): spigot D62h7 x 10 (joint x 46.5..56.5), face x 56.5, 16 x M3 on PCD54 at
18/36/54/72 + 90k deg, the input shaft D25 (bore D19..D20, hollow) ends flush with the output face and turns at motor speed.
Adapter:
  skirt OD80 z 0..9, bore D62H7 x 9 on the spigot (the floor bears on the output face at z 9);
  floor z 9..15: 16 x D3.4 on PCD54, counterbores D6.5 x 3.5 from the cavity (M3x12 DIN912 from the inside),
     relief D27 x 1 under the floor (clear of the turning input-shaft end), centre hole D16H7 for the cable tube;
  cup z 15..H: OD90 = sensor, cavity D66, top face = sensor mounting face;
     6 x M5 x 10 (drill D4.2 x 12) on PCD78 at 0 + 60k deg (sensor bolts from the tool side, through its D5.5 holes),
     2 x pin hole D5H7 x 6 on PCD78 at 26 / 206 deg (as the sensor, assumed);
  cable window: slot 8 wide from the top face down to the floor, radial through the wall at -76 deg (between the sensor
     cable boss at -90 deg and the M5 at -60 deg, under the boss exit which points to +X): the cable D3 leaves the boss,
     bends down into the slot, crosses the cavity floor to the centre and goes down the tube.
Cable tube (separate body): 16 x 1 (ID14 - cable D3 with a connector up to ~D13), collar D22 x 1.5 on the floor top,
   through the hollow input shaft (bore D19, clearance 1.5 radial) - the tube turns with the output, the input shaft
   turns around it without touching the cable. Length to the J7 back end - to be fixed when the cable route in link 6 is set.
Writes components/Kunwei/KWR90/KWR90-J7-adapter.STEP (adapter), KWR90-J7-stack.STEP (adapter + tube + sensor + cable,
   in the adapter frame) and previews.
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
import make_kwr90 as kw
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir, gp_Trsf, gp_Vec, gp_Ax1
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound

H, Z_FLOOR0, Z_FLOOR1 = 35.0, 9.0, 15.0
D_SKIRT, D_FIT, D_TOP, D_CAV = 80.0, 62.0, 90.0, 66.0
SLOT_ANG, SLOT_W = -76.0, 8.0
J7_X0 = 47.5                     # joint x of the adapter bottom (z = 0)
TUBE_OD, TUBE_ID, TUBE_L = 16.0, 14.0, 75.0

cyl, polar = kw.cyl, kw.polar

def moved(s, dx=0, dy=0, dz=0, rot_z=0.0):
    t = gp_Trsf()
    if rot_z: t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(rot_z))
    t2 = gp_Trsf(); t2.SetTranslation(gp_Vec(dx, dy, dz)); t2.Multiply(t)
    return BRepBuilderAPI_Transform(s, t2, True).Shape()

def adapter():
    s = BRepAlgoAPI_Fuse(cyl(0, 0, 0, D_SKIRT, Z_FLOOR1), cyl(0, 0, Z_FLOOR0, D_TOP, H - Z_FLOOR0)).Shape()
    cuts = [cyl(0, 0, -1, D_FIT, Z_FLOOR0 + 1),                        # D62H7 x 9
            cyl(0, 0, Z_FLOOR0 - 0.01, 27.0, 1.01),                    # relief over the input shaft end
            cyl(0, 0, -1, TUBE_OD, H + 2),                             # D16H7 for the tube
            cyl(0, 0, Z_FLOOR1, D_CAV, H)]                             # cavity
    for a0 in (18, 36, 54, 72):
        for k in range(4):
            x, y = polar(54, a0 + 90 * k)
            cuts.append(cyl(x, y, -1, 3.4, H)); cuts.append(cyl(x, y, Z_FLOOR1 - 3.5, 6.5, 4.0))
    for k in range(6):
        x, y = polar(78, 60 * k); cuts.append(cyl(x, y, H + 0.01, 4.2, 12.01, down=True))
    for deg in (26, 206):
        x, y = polar(78, deg); cuts.append(cyl(x, y, H + 0.01, 5.0, 6.01, down=True))
    slot = BRepPrimAPI_MakeBox(gp_Pnt(D_CAV / 2 - 2, -SLOT_W / 2, Z_FLOOR1), D_TOP / 2 - D_CAV / 2 + 6, SLOT_W,
                               H - Z_FLOOR1 + 1).Shape()
    cuts.append(moved(slot, rot_z=SLOT_ANG))
    for c in cuts: s = BRepAlgoAPI_Cut(s, c).Shape()
    return s

def tube():
    s = BRepAlgoAPI_Fuse(cyl(0, 0, Z_FLOOR1 - TUBE_L, TUBE_OD, TUBE_L + 1.5), cyl(0, 0, Z_FLOOR1, 22.0, 1.5)).Shape()
    return BRepAlgoAPI_Cut(s, cyl(0, 0, Z_FLOOR1 - TUBE_L - 1, TUBE_ID, TUBE_L + 4)).Shape()

def vol(s):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g); return g.Mass()

def write(shapes, path):
    comp = TopoDS_Compound(); bb = BRep_Builder(); bb.MakeCompound(comp)
    for s in shapes: bb.Add(comp, s)
    w = STEPControl_Writer(); w.Transfer(comp, STEPControl_AsIs); w.Write(path)

# cable route in the adapter frame: boss exit (sensor x 9, y -49, z 6) -> down the slot -> centre -> down the tube
def cable_path():
    a = math.radians(SLOT_ANG); c, s_ = math.cos(a), math.sin(a)
    r = lambda rr, z: (rr * c, rr * s_, z)
    return [(9.0, -49.0, H + 6), (15.0, -49.0, H + 5.5), (14.5, -47.0, H + 1.5), r(44, H - 4), r(38, Z_FLOOR1 + 7),
            r(26, Z_FLOOR1 + 3), r(10, Z_FLOOR1 + 2.5), (0, 0, Z_FLOOR1 - 4), (0, 0, Z_FLOOR1 - 40)]

if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "components", "Kunwei", "KWR90")
    ad, tb = adapter(), tube()
    sen = moved(kw.build(), dz=H); cab = moved(kw.cable(), dz=H)
    write([ad], os.path.join(out, "KWR90-J7-adapter.STEP"))
    write([ad, tb, sen, cab], os.path.join(out, "KWR90-J7-stack.STEP"))
    for nm, s, rho in (("adapter", ad, 2.7e-6), ("tube", tb, 2.7e-6)):
        print(f"{nm}: {vol(s) / 1e3:.1f} cm3, {vol(s) * rho:.3f} kg aluminium")
    # checks: no overlap adapter/sensor, adapter/tube
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    for nm, b in (("sensor", sen), ("tube", tb)):
        print(f"overlap adapter-{nm}: {vol(BRepAlgoAPI_Common(ad, b).Shape()):.3f} mm3")
    a = math.radians(-60); hx, hy = 39 * math.cos(a), 39 * math.sin(a)
    b = math.radians(SLOT_ANG)
    d = abs(-hx * math.sin(b) + hy * math.cos(b)) - SLOT_W / 2 - 2.1
    print(f"wall slot - M5 drill at -60 deg: {d:.1f} mm; stack top = joint x {J7_X0 + H + kw.H:.1f} (J7 face 56.5)")
