"""Joint ranges without contacts of the user's full arm (tools/gen_user_full.py geometry): each joint Jk is turned
alone (the others at zero), the moving chain (everything after Jk) is checked against the rest + the mounting plane
(bottom of the base plate x=-12).   python tools/sweep_user_full.py J2 J3 J4 ... [--step 10]"""
import sys, os, math; sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, glob, link_build as lb, joint_envelope as je, gen_user_full as gf, gen_user_l123 as g
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir
def mv(s,T):
    t=gp_Trsf(); t.SetValues(*[float(v) for v in T[:3,:].ravel()]); return BRepBuilderAPI_Transform(s,t,True).Shape()
def load(f):
    r=STEPControl_Reader(); r.ReadFile(f); r.TransferRoots(); return r.OneShape()
order=["B","J1","L1","J2","L2","J3","L3","J4","L4","J5","L5","J6","L6","J7","F"]
P=[]
for f in glob.glob("links-user/LINK-1U/assembly-parts/*.step"):
    n=os.path.basename(f)[:-5]
    if n=="J1-J2" or not n.isascii() or n.startswith(("DMRD-80E","SHM-1000","AK80","DMRD-KB25","SHM-KB25")): continue
    P.append((n,load(f),"B"))      # the user's ОПУ etc. (fixed)
T1=g.frame([171,16.5826773713467,83.3667488342793],[1,0,0],[0,0.195090322015843,0.980785280403287])
P+=[("LINK-1U",mv(lb.build_part(lb.parse("links-user/LINK-1U/LINK-1U.txt")[0][0]),T1),"L1"),
    ("YULA",lb.build_part(lb.parse("links-user/YULA/YULA.txt")[0][0]),"L1"),
    ("BASEPLATE",lb.build_part(lb.parse("links-user/BASEPLATE/BASEPLATE.txt")[0][0]),"B"),
    ("LINK-2B",mv(lb.build_part(lb.parse("links-user/LINK-2B/LINK-2B.txt")[0][0]),g.L2),"L2")]
for n in ("L3","L4","L5","L6"):
    P.append(("LINK-"+n[1],mv(lb.build_part(lb.parse(gf.comps[n][0])[0][0]),gf.place(n)),n))
_all=je.all_joints; kb17=dict(_all()["SHM-KB17"]); kb17["x_out"]=59.5
je.all_joints=lambda: {**_all(),"SHM-KB50":_all()["SHM-KB50F"],"SHM-60":kb17}
J2v2=gf.comps["J2"][1]; J1v2=gf.comps["J1"][1]
for nm,s,jn,kind in lb.envelope_solids("robot/RTC-7-layout-v2.txt",["J1","J2","J3","J4","J5","J6","J7"]):
    if jn=="base": continue
    if jn=="J1": Tn=g.frame([-33.5,0,0],[1,0,0],[0,-0.5,0.866025])@np.linalg.inv(J1v2)
    elif jn=="J2": Tn=g.J2@np.linalg.inv(J2v2)
    else: Tn=gf.place(jn)
    # moving part of a joint (output shaft) belongs to the next link
    grp=jn if kind!="rot" or "Output" not in nm else order[order.index(jn)+1]
    P.append((jn+" "+nm,mv(s,Tn),grp))
# joint axes in the assembly frame
def axis(name):
    if name=="J1": return np.array([0,0,0.]),np.array([1.,0,0])
    if name=="J2": return g.J2[:3,3],g.J2[:3,0]
    T=gf.M@gf.comps[name][1]; return T[:3,3],T[:3,0]
def bb(s):
    b=Bnd_Box(); BRepBndLib.Add_s(s,b); return b
step=10
for a in sys.argv[1:]:
    if a.startswith("--step"): step=int(a.split("=")[1])
for J in [a for a in sys.argv[1:] if a.startswith("J")]:
    k=order.index(J); mov=[p for p in P if order.index(p[2])>k]; fix=[p for p in P if order.index(p[2])<k]
    # the joint itself (its fixed parts) belongs to fix; skip the pair link(k) / joint k parts (in contact by design)
    fix+= [p for p in P if p[2]==J]
    o,d=axis(J); ax=gp_Ax1(gp_Pnt(*map(float,o)),gp_Dir(*map(float,d)))
    res=[]
    for ang in range(-180,181,step):
        r=gp_Trsf(); r.SetRotation(ax,math.radians(ang)); hit=[]; low=1e9
        for a in mov:
            sa=BRepBuilderAPI_Transform(a[1],r,True).Shape(); ba=bb(sa); low=min(low,ba.CornerMin().X())
            for b in fix:
                if order.index(a[2])==k+1 and order.index(b[2])==k: continue   # link on its own joint
                if ba.IsOut(bb(b[1])): continue
                v=lb.volume(BRepAlgoAPI_Common(sa,b[1]).Shape())[0]
                if v>1: hit.append(f"{a[0]}/{b[0]}")
        floor= low < -12
        res.append((ang,hit,floor,low)); print(J,ang,"OK" if not hit else hit[:2],"FLOOR %.0f"%low if floor else "",flush=True)
