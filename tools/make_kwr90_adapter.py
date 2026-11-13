"""Adapter J7 output (DMRD-KB17) -> 6-axis F/T sensor Kunwei KWR90, LOW variant (user 2026-11-12: "the lowest").
The sensor cable goes under the sensor through a radial groove in the adapter top face into the centre of the joint.

Frame: Z - the J7 axis, z = 0 - the adapter bottom (J7 side) = joint x 47.5 (1 mm from the reducer housing face x 46.5),
z = H = 19 - the top face = the sensor mounting face (sensor z = 0). Stack: sensor tool face at joint x 90.5 (J7 face 56.5).
J7 output (DMRD-KB17-03_OutputShaft): spigot D62h7 x 10, face x 56.5, 16 x M3 on PCD54 at 18/36/54/72 + 90k deg (holes:
D3.5 x 9 smooth, then M3 x 6), the hollow input shaft (bore D19) ends flush with the face and turns at motor speed.
Adapter (aluminium, 0.20 kg):
  skirt OD80 z 0..9, bore D62H7 x 9; relief D27 x 1 over the input-shaft end;
  plate OD90 z 9..19;
  16 x D3.4 through, counterbores D6.5 from the top to z 14 - M3x20 DIN7984 (low head) = full 6 mm thread in the shaft;
     the J7 pattern is clocked +16 deg against the sensor so that its free axis lies under the cable groove
     (the sensor frame is turned 16 deg against J7 zero - compensate in the F/T software);
  6 x M5 on PCD78 at 0 + 60k: Helicoil M5 x 1.5D (drill D5.2 x 9.5) - aluminium, short thread;
  2 x pin D5H7 x 6 on PCD78 at 26 / 206 deg (as the sensor, assumed);
  cable groove 4.5 wide x 4.5 deep, radial at -74 deg (right next to the sensor cable boss at -90, whose cable leaves
     towards +X): cable D3 centre 3 mm under the sensor face, walls to the M3 counterbores 2.8, to the M5 4.6 mm;
  central pocket D22 from z 11.5 (tube collar seat) - the cable bends down with R 12 into the tube.
Cable tube (separate body, 0.01 kg): 16 x 1 (ID14), collar D22 x 1.5 at z 11.5..13, through the hollow input shaft
   (clearance 1.5 radial), fixed with Loctite 638; length to be set with the cable route in link 6.
Outside the adapter the cable makes a loop R ~10 from the boss exit (+X) back into the groove.
Writes components/Kunwei/KWR90/KWR90-J7-adapter.STEP, KWR90-J7-stack.STEP (adapter + tube + sensor + cable) + preview.
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

H, Z_SKIRT = 19.0, 9.0          # low variant (user 2026-11-12): plate instead of the cup
D_SKIRT, D_FIT, D_TOP = 80.0, 62.0, 90.0
CLOCK = 16.0                     # the J7 M3 pattern turned by +16 deg against the sensor: its free axis -> -74 deg
GROOVE_ANG, GROOVE_W, GROOVE_D = -74.0, 4.5, 4.5     # radial cable groove in the top face (cable D3 centre H - 3)
POCKET_D, POCKET_Z0 = 22.0, 11.5                     # central pocket for the bend + the tube collar
CB_D, CB_Z = 6.5, 14.0                               # M3 DIN7984 counterbores from the top, head bearing z 14
M5_DRILL, M5_DEPTH = 5.2, 9.5                        # Helicoil M5 x 1.5D (7.5) drill
J7_X0 = 47.5                     # joint x of the adapter bottom (z = 0)
TUBE_OD, TUBE_ID, TUBE_L, TUBE_TOP = 16.0, 14.0, 75.0, 13.0
SLOT_ANG = GROOVE_ANG

cyl, polar = kw.cyl, kw.polar

def moved(s, dx=0, dy=0, dz=0, rot_z=0.0):
    t = gp_Trsf()
    if rot_z: t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(rot_z))
    t2 = gp_Trsf(); t2.SetTranslation(gp_Vec(dx, dy, dz)); t2.Multiply(t)
    return BRepBuilderAPI_Transform(s, t2, True).Shape()

def m3_angles():
    return [a0 + 90 * k + CLOCK for a0 in (18, 36, 54, 72) for k in range(4)]

def adapter():
    s = BRepAlgoAPI_Fuse(cyl(0, 0, 0, D_SKIRT, Z_SKIRT + 0.5), cyl(0, 0, Z_SKIRT, D_TOP, H - Z_SKIRT)).Shape()
    cuts = [cyl(0, 0, -1, D_FIT, Z_SKIRT + 1),                         # D62H7 x 9
            cyl(0, 0, Z_SKIRT - 0.01, 27.0, 1.01),                     # relief over the input shaft end
            cyl(0, 0, -1, TUBE_OD, H + 2),                             # D16H7 for the tube
            cyl(0, 0, POCKET_Z0, POCKET_D, H)]                         # pocket D22: tube collar + cable bend
    for a in m3_angles():
        x, y = polar(54, a)
        cuts.append(cyl(x, y, -1, 3.4, H)); cuts.append(cyl(x, y, CB_Z, CB_D, H))
    for k in range(6):
        x, y = polar(78, 60 * k); cuts.append(cyl(x, y, H + 0.01, M5_DRILL, M5_DEPTH + 0.01, down=True))
    for deg in (26, 206):
        x, y = polar(78, deg); cuts.append(cyl(x, y, H + 0.01, 5.0, 6.01, down=True))
    g = BRepPrimAPI_MakeBox(gp_Pnt(POCKET_D / 2 - 2, -GROOVE_W / 2, H - GROOVE_D), D_TOP / 2 - POCKET_D / 2 + 6,
                            GROOVE_W, GROOVE_D + 1).Shape()
    cuts.append(moved(g, rot_z=GROOVE_ANG))
    for c in cuts: s = BRepAlgoAPI_Cut(s, c).Shape()
    return s

def tube():
    s = BRepAlgoAPI_Fuse(cyl(0, 0, TUBE_TOP - TUBE_L, TUBE_OD, TUBE_L), cyl(0, 0, POCKET_Z0, 22.0, TUBE_TOP - POCKET_Z0)).Shape()
    return BRepAlgoAPI_Cut(s, cyl(0, 0, TUBE_TOP - TUBE_L - 1, TUBE_ID, TUBE_L + 4)).Shape()

# second adapter sensor tool side -> SZU (CONCEPT, not detailed yet): plate D80 x 6 on the sensor tool boss D48 (6 x M5
# DIN912 on PCD40 from inside the spigot, 2 pins D5), spigot D62h7 x 11 / ID50 for the SZU recess D62H7 x 10 + its
# 20 x M3 on PCD54; SZU port (recess bottom) at joint x 90.5 + 6 + 11 = 107.5 = J7 face 56.5 + FTS_DX
A2_T, A2_SPIG = 6.0, 11.0
FTS_DX = J7_X0 + H + kw.H + A2_T + A2_SPIG - 56.5          # SZU shift along the J7 axis, mm (= 51)
FTS_EXTRA_KG = 0.05                                         # screws, pins, Helicoils, cable in the stack

def adapter2():
    z0 = H + kw.H
    s = BRepAlgoAPI_Fuse(cyl(0, 0, z0, 80.0, A2_T), cyl(0, 0, z0 + A2_T - 0.01, 62.0, A2_SPIG + 0.01)).Shape()
    for c in (cyl(0, 0, z0 - 1, 30.0, A2_T + 2), cyl(0, 0, z0 + A2_T, 50.0, A2_SPIG + 1)):
        s = BRepAlgoAPI_Cut(s, c).Shape()
    return s

def stack_shapes():
    """[(name, shape)] of the F/T stack in the adapter frame (z = 0 at joint x 47.5)."""
    return [("adapter", adapter()), ("tube", tube()), ("sensor", moved(kw.build(), dz=H)), ("adapter2", adapter2())]

def vol(s):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g); return g.Mass()

def write(shapes, path):
    comp = TopoDS_Compound(); bb = BRep_Builder(); bb.MakeCompound(comp)
    for s in shapes: bb.Add(comp, s)
    w = STEPControl_Writer(); w.Transfer(comp, STEPControl_AsIs); w.Write(path)

# cable route in the adapter frame: boss exit (sensor x 9, y -49, z 6) -> down the slot -> centre -> down the tube
def cable_path():
    a = math.radians(GROOVE_ANG); c, s_ = math.cos(a), math.sin(a)
    r = lambda rr, z: (rr * c, rr * s_, z)
    zc = H - GROOVE_D + 1.5; R = 12.0; ze = zc - R
    pts = [(9.0, -49.0, H + 6), (15.0, -50.5, H + 4.5), (17.5, -49.0, H + 1.0), r(47, zc + 0.5), r(40, zc), r(R + 2, zc)]
    for k in range(1, 9):                                   # bend R12 down into the tube
        f = math.radians(90 - 90 * k / 8); pts.append(r(R * (1 - math.cos(f)), ze + R * math.sin(f)))
    return pts + [(0, 0, ze - 40)]

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
    ga = math.radians(GROOVE_ANG)
    def off(pcd, deg):
        x, y = polar(pcd, deg); return abs(-x * math.sin(ga) + y * math.cos(ga)), x * math.cos(ga) + y * math.sin(ga)
    walls = [off(54, a)[0] - CB_D / 2 - GROOVE_W / 2 for a in m3_angles() if off(54, a)[1] > 0]
    walls5 = [off(78, 60 * k)[0] - M5_DRILL / 2 - GROOVE_W / 2 for k in range(6) if off(78, 60 * k)[1] > 0]
    print(f"wall groove - M3 counterbore {min(walls):.1f}, groove - M5 {min(walls5):.1f} mm")
    print(f"stack top = joint x {J7_X0 + H + kw.H:.1f} (J7 face 56.5)")
