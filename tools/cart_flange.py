"""Lower robot flange of the cart hull (user 2026-11-12: minimise the robot height over the deck).

The hull model (platform/CART/KORPUS.STEP) carries the robot flange as a disc D240 x 30 (y 520..550) with the bore D150
and 12 x D9 on PCD217, welded on the deck plate (top y = 520). Here the disc is cut down to h mm over the deck; the bore
and the holes stay (their depth = h). Writes platform/CART/KORPUS_F<h>.STEP.

    python tools/cart_flange.py 12                    -> KORPUS_F12.STEP
    CART_FLANGE_H=12 python tools/cart_reach.py ...   -> studies with the lower flange (cart_layout.FLANGE_H)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import cart_layout as cl
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

def make(h, out=None):
    src = os.path.join(cl.CART_DIR, "KORPUS.STEP")
    r = STEPControl_Reader(); r.ReadFile(src); r.TransferRoots(); sh = r.OneShape()
    top = cl.DECK_Y + cl.FLANGE_H0
    cut_h = top - (cl.DECK_Y + h)
    tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(cl.FLANGE_C[0], cl.DECK_Y + h, cl.FLANGE_C[1]), gp_Dir(0, 1, 0)),
                                    120.5, cut_h + 1.0).Shape()
    res = BRepAlgoAPI_Cut(sh, tool).Shape()
    def vol(s):
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g); return g.Mass()
    dv = vol(sh) - vol(res)
    out = out or os.path.join(cl.CART_DIR, f"KORPUS_F{h:g}.STEP")
    w = STEPControl_Writer(); w.Transfer(res, STEPControl_AsIs); w.Write(out)
    print(f"flange {cl.FLANGE_H0:g} -> {h:g} mm: removed {dv / 1e3:.0f} cm3 ({dv * 7.85e-6:.2f} kg of steel), {out}")
    return out

if __name__ == "__main__":
    for a in sys.argv[1:]:
        make(float(a))
