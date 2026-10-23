import sys, re, os
from OCP.IGESControl import IGESControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SHELL, TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.ShapeFix import ShapeFix_Solid
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
path, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
lines=open(path,"rb").read().decode("cp1251",errors="replace").splitlines()
D=[l for l in lines if len(l)>=73 and l[72]=='D']; P={}
for l in lines:
    if len(l)>=73 and l[72]=='P':
        P.setdefault(int(l[64:72]),[]).append(l[:64])
import numpy as np
iv=lambda s: int(s) if s.strip() else 0
typ={i+1:int(D[i][0:8]) for i in range(0,len(D),2)}
tmp={i+1:iv(D[i][48:56]) for i in range(0,len(D),2)}
def nums(de): return "".join(P[de]).replace(" ","").strip(";").split(",")
def M4(de):
    if not de: return np.eye(4)
    v=[float(x) for x in nums(de)[1:13]]; m=np.eye(4); m[:3,:]=np.array(v).reshape(3,4); return m
defs={}
for de,t in typ.items():
    if t==308:
        raw="".join(P[de]); m=re.match(r"\s*308,\s*0,\s*(\d+)H",raw); n=int(m.group(1)); s0=m.end(); name=raw[s0:s0+n].strip()
        rest=raw[s0+n:].replace(" ","").strip(",;").split(",")
        cnt=int(rest[0]); mem=[int(x) for x in rest[1:1+cnt]]
        defs[de]=(name,mem)
roots=[de for de,t in typ.items() if t==408 and not tmp[de]]
groups=[]
def walk(d308,M,path):
    name,mem=defs[d308]
    surf=[x for x in mem if typ.get(x) in (144,128,143)]
    if surf: groups.append((name,surf,M,path))
    for x in mem:
        if typ.get(x)==408:
            c=int(nums(x)[1]); walk(c, M@M4(tmp[x]), path+"/"+defs[c][0])
for r0 in roots:
    c=int(nums(r0)[1]); walk(c,np.eye(4),defs[c][0])
r=IGESControl_Reader(); r.ReadFile(path)
res=[]
from OCP.gp import gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
for name,surf,M,path in groups:
    r.ClearShapes()
    for de in surf: r.TransferOne((de+1)//2)
    sew=BRepBuilderAPI_Sewing(0.01)
    for k in range(1,r.NbShapes()+1): sew.Add(r.Shape(k))
    sew.Perform(); sh=sew.SewedShape()
    tr=gp_Trsf(); tr.SetValues(*[float(v) for v in M[:3,:].ravel()]); sh=BRepBuilderAPI_Transform(sh,tr,True).Shape()
    solids=[]; e=TopExp_Explorer(sh,TopAbs_SHELL)
    while e.More():
        ms=BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(e.Current()) if hasattr(TopoDS,"Shell_s") else TopoDS.Shell(e.Current()))
        so=ms.Solid(); fx=ShapeFix_Solid(so); fx.Perform(); so=fx.Solid()
        g=GProp_GProps(); BRepGProp.VolumeProperties_s(so,g)
        if g.Mass()<0: so.Reverse(); BRepGProp.VolumeProperties_s(so,g)
        solids.append((so,g.Mass(),g.CentreOfMass())); e.Next()
    for i,(so,v,c) in enumerate(solids):
        b=Bnd_Box(); BRepBndLib.Add_s(so,b); p0,p1=b.CornerMin(),b.CornerMax()
        fn=os.path.join(outdir,f"{name}{'' if len(solids)==1 else '_'+str(i)}.step")
        w=STEPControl_Writer(); w.Transfer(so,STEPControl_AsIs); w.Write(fn)
        print(f"{path:60s} faces {len(surf):4d} vol {v/1e3:9.2f} cm3  x {p0.X():7.1f}..{p1.X():7.1f} y {p0.Y():7.1f}..{p1.Y():7.1f} z {p0.Z():7.1f}..{p1.Z():7.1f}")
