import sys, glob, os, math; sys.path.insert(0,'/home/claude/rtc/tools')
import numpy as np, pyvista as pv, link_build as lb
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.gp import gp_Trsf
pv.global_theme.allow_empty_mesh=True
XJ2=np.array([0,0.195090322015843,0.980785280403287]); ZR=np.array([1.0,0,0]); YR=np.cross(ZR,XJ2)
face=np.array([171,-1.95090322015508,-9.80785280403365])+149*XJ2
O=face-137*ZR
def T_robot():
    t=gp_Trsf(); R=np.c_[XJ2,YR,ZR]; t.SetValues(*[float(v) for v in np.c_[R,O].ravel()]); return t
TR=T_robot()
from OCP.gp import gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
TSH=gp_Trsf(); TSH.SetTranslation(gp_Vec(-139-135,0,420-365))
t1=gp_Trsf(); t1.SetValues(1.,0.,0.,171.,0.,0.980785280403287,0.195090322015843,16.5826773713467,0.,-0.195090322015843,0.980785280403287,83.3667488342793)
def load(f):
    r=STEPControl_Reader(); r.ReadFile(f); r.TransferRoots(); return r.OneShape()
parts=[]
for f in glob.glob("links-user/LINK-1U/assembly-parts/*.step"):
    n=os.path.basename(f)[:-5]
    if n in ("J1-J2","Юла","Пластина переходная"): continue
    parts.append((n,load(f),"user"))
parts.append(("LINK-1U",BRepBuilderAPI_Transform(lb.build_part(lb.parse("links-user/LINK-1U/LINK-1U.txt")[0][0]),t1,True).Shape(),"link1"))
parts.append(("YULA",lb.build_part(lb.parse("links-user/YULA/YULA.txt")[0][0]),"yula"))
parts.append(("BASEPLATE",lb.build_part(lb.parse("links-user/BASEPLATE/BASEPLATE.txt")[0][0]),"base"))
parts.append(("LINK-2U",BRepBuilderAPI_Transform(lb.build_part(lb.parse("links-user/LINK-2U/LINK-2U.txt")[0][0]),TR,True).Shape(),"link2"))
for nm,s,jn,kind in lb.envelope_solids("robot/RTC-7-layout-v2.txt",["J3"]):
    if jn=="J3":
        s=BRepBuilderAPI_Transform(s,TSH,True).Shape()
        parts.append(("J3 "+nm,BRepBuilderAPI_Transform(s,TR,True).Shape(),"J3"+kind))
# interference of the new parts with the user's ones
newp=[p for p in parts if p[2] in ("link2",) or p[2].startswith("J3")]
oldp=[p for p in parts if p not in newp]
for a in newp:
    for b in oldp:
        v=lb.volume(BRepAlgoAPI_Common(a[1],b[1]).Shape())[0]
        if v>1: print("OVERLAP",a[0],b[0],round(v))
print("J3 axis: point",np.round(O-139*XJ2,2),"dir",ZR," dist from J1 axis",round(np.hypot(*(O-139*XJ2)[1:]),1))
import os as _o
if _o.environ.get("SWEEP"):
    ax=gp_Ax1(gp_Pnt(*[float(v) for v in O+137*ZR]),gp_Dir(*[float(v) for v in XJ2]))
    for ang in range(-180,181,15):
        r=gp_Trsf(); r.SetRotation(ax,math.radians(ang)); hit=[]
        for a in newp:
            sa=BRepBuilderAPI_Transform(a[1],r,True).Shape()
            for b in oldp:
                if b[0].startswith("SHM-1000") or "80E" in b[0] or "AK80" in b[0] and False: pass
                v=lb.volume(BRepAlgoAPI_Common(sa,b[1]).Shape())[0]
                if v>1: hit.append((a[0],b[0],round(v)))
        print("J2",ang,"OK" if not hit else hit[:4])
def mesh(s):
    tri=np.array(lb.triangles(s,0.4)); pts=tri.reshape(-1,3)
    return pv.PolyData(pts,np.hstack([np.full((len(tri),1),3),np.arange(len(pts)).reshape(-1,3)]).ravel()).clean()
def col(n,k):
    if k=="link1": return "#d49a90"
    if k=="link2": return "#e0b93c"
    if k=="yula": return "#6fae5a"
    if k=="base": return "#c8a0c8"
    if "Flange" in n: return "#2a5d9f"
    if "RU178G" in n: return "#9aa1a8"
    if "AK80" in n or k.endswith("motor"): return "#2f3338"
    if "OutputShaft" in n or k.endswith("rot"): return "#7fae6e"
    if k.endswith("cover"): return "#d5dade"
    return "#b8c2cc"
M=[(mesh(s),col(n,k)) for n,s,k in parts]
pl=pv.Plotter(off_screen=True, window_size=(2400,1100), shape=(1,3))
side=np.cross(XJ2,ZR)
for i,(cam,t) in enumerate((((-0.6,-1,0.9),"J1-J2-J3 (user's J1-J2 + our link 2 and J3), X = J1 axis up"),(tuple(side),"side view (across the J2 axis)"),(tuple(XJ2*1+ZR*0.15),"along the J2 axis, from the J3 side"))):
    pl.subplot(0,i); pl.set_background("white")
    for m,c in M: pl.add_mesh(m,color=c,specular=0.25)
    pl.view_vector(cam,viewup=(1,0,0)); pl.reset_camera(); pl.camera.zoom(1.2); pl.add_text(t,font_size=10,color="black")
pl.screenshot(sys.argv[1]); print("->",sys.argv[1])
