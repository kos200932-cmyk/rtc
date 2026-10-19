#!/usr/bin/env python3
"""Strength check input of the links (Ansys Workbench 2024 R1): geometry, interfaces, load cases.

    python tools/fea_export.py [--out fea/RTC-7] [--payload 8] [--sf 1.5]

For every link (LINK-1 .. LINK-6 weldments, plus the J1 adapter of link 1 as its own model):
  * geometry/<model>.step - the part in the global frame of the arm at the zero pose (mm), the contact
    areas of the interfaces imprinted on its faces (split by the flange circle), so they are separate faces;
  * interfaces: FIXED - where the part sits on the previous joint (output shaft / ОПУ ring), LOAD - where
    the next joint housing sits on it; each = planar contact faces + the pilot cylinder (H7 fit);
    selected in Mechanical by the same geometric rules that are checked here on the STEP (areas);
  * load cases (all from the URDF model sim/RTC-7/RTC-7.urdf, Pinocchio):
      S  - static, gravity, payload --payload kg + interface 4 kg, the pose with the largest moment at the
           fixed interface (search over J2..J7 within the joint ranges);
      D  - the largest moment along the demo program (robot/RTC-7-demo.txt), with accelerations;
      C  - blocked tool (collision / emergency): at the S pose the tool is held by an obstacle and the drives
           push until the first joint reaches the reducer PEAK torque (catalog T_peak); the force direction
           at the TCP is searched for the largest moment at the fixed interface (gravity included).
           (A rigid-body braking with T_peak gives unreal decelerations on the wrist axes - hundreds to
           thousands of rad/s^2 - so it is not used.)
    for each case: force F [N] and moment M [N*mm] applied BY the next joint housing ON the part, at the
    LOAD remote point (interface centre), components in the global frame of the STEP; the acceleration
    field of the part itself (gravity + its own acceleration at its centre of mass, mm/s^2, Ansys
    "Acceleration" convention: the acceleration of the body, gravity = +9806.6 along +Z when the arm
    is upright); the EXPECTED reaction at the FIXED remote point (to check the model in Ansys);
  * fea/RTC-7/rtc7_fea.json - all of it for the Workbench / Mechanical scripts; cards/<model>.md - the
    description of every part (option "a"); pictures/<model>.png - the interface faces.
Bolted joints and welds are not modelled: the part is one solid, the FIXED faces are rigidly fixed (bolted
joint = bonded), the LOAD faces are joined rigidly to the remote point. The own rotation (centrifugal /
angular acceleration) of the part is applied through its centre-of-mass acceleration only (small).
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAT = {"name": "AMg6", "E_MPa": 69600.0, "nu": 0.30, "rho": 2640.0, "Sy_MPa": 155.0, "Su_MPa": 315.0,
       "weld_factor": 0.9,
       "source": "АМг6М листы 0,6-10,5 мм, ГОСТ 21631 (каталог ВИАМ): sigma_v >= 315, sigma_0.2 >= 155 МПа, "
                 "E 69,6 ГПа, 2640 кг/м3; nu 0.30 и коэффициент прочности шва 0.9 - ПРИНЯТЫ"}
T_PEAK = {"SHM-150m": 310.0, "SHM-150": 310.0, "SHM-1000": 3920.0, "SHM-500": 1350.0, "SHM-60": 186.0}
G = 9.80665

# interfaces from the PORTP lines of links/LINK-n (plane axis, coordinate, fit, bolts) + the joint axes;
# kind "out": the part sits on a joint output (contact inside the fit circle), "base": a joint housing
# sits on the part (contact from the fit circle to the flange circle PCD/2 + 1.6 d), "ring": ОПУ ring.
MODELS = [
    {"id": "LINK-1", "parts": ["LINK-1/LINK-1-01_Weldment"], "k": 1, "mesh_mm": 5.0,
     "fixed": {"name": "j1_ring", "axis": "Z", "coord": 0.0, "center": (0, 0, 0), "kind": "ring", "fit": 112, "r_max": 80.0,
               "role": "на внутреннем кольце ОПУ RU178G (12xM8 D139)"},
     "load": {"name": "j2_base", "axis": "X", "coord": -95.0, "center": (-95, 0, 137), "kind": "base", "fit": 190, "pcd": 206, "bolt": 8,
              "role": "корпус J2 (ШМ-1000, 190H7, 16xM8 D206)"}},
    {"id": "LINK-1A", "parts": ["LINK-1/LINK-1-02_J1Adapter"], "k": 1, "mesh_mm": 3.0, "adapter": True,
     "fixed": {"name": "j1_output", "axis": "Z", "coord": -35.0, "center": (0, 0, -35), "kind": "out", "fit": 112, "pcd": 100, "bolt": 5,
               "role": "на выходном валу J1 (ШМ-150м, 112H7, 16xM5 D100)"},
     "load": {"name": "ring", "axis": "Z", "coord": -28.0, "center": (0, 0, -28), "kind": "ring", "fit": 112, "r_max": 77.5,
              "role": "под внутренним кольцом ОПУ (крутящий момент J1)"}},
    {"id": "LINK-2", "parts": ["LINK-2/LINK-2-01_Weldment"], "k": 2, "mesh_mm": 5.0,
     "fixed": {"name": "j2_out", "axis": "X", "coord": 0.0, "center": (0, 0, 137), "kind": "out", "fit": 160, "pcd": 142, "bolt": 8,
               "role": "на выходном валу J2 (ШМ-1000, 160H7, 9xM8 D142 + 6xM10 D110)"},
     "load": {"name": "j3_base", "axis": "Z", "coord": 276.0, "center": (105, 0, 276), "kind": "base", "fit": 168, "pcd": 180, "bolt": 6,
              "role": "корпус J3 (ШМ-500, 168H7, 9xM6 D180)"}},
    {"id": "LINK-3", "parts": ["LINK-3/LINK-3-01_Weldment"], "k": 3, "mesh_mm": 5.0,
     "fixed": {"name": "j3_out", "axis": "Z", "coord": 365.0, "center": (105, 0, 365), "kind": "out", "fit": 158, "pcd": 140, "bolt": 8,
               "role": "на выходном валу J3 (ШМ-500, 158H7, 16xM8 D140)"},
     "load": {"name": "j4_base", "axis": "X", "coord": -11.0, "center": (-11, 0, 1467), "kind": "base", "fit": 168, "pcd": 180, "bolt": 6,
              "role": "корпус J4 (ШМ-500, 168H7, 9xM6 D180)"}},
    {"id": "LINK-4", "parts": ["LINK-4/LINK-4-01_Weldment"], "k": 4, "mesh_mm": 4.0,
     "fixed": {"name": "j4_out", "axis": "X", "coord": -100.0, "center": (-100, 0, 1467), "kind": "out", "fit": 158, "pcd": 140, "bolt": 8,
               "role": "на выходном валу J4 (ШМ-500, 158H7, 16xM8 D140)"},
     "load": {"name": "j5_base", "axis": "Z", "coord": 1568.0, "center": (-174, 0, 1568), "kind": "base", "fit": 122, "pcd": 132, "bolt": 5,
              "role": "корпус J5 (ШМ-150, 122H7, 12xM5 D132)"}},
    {"id": "LINK-5", "parts": ["LINK-5/LINK-5-01_Weldment"], "k": 5, "mesh_mm": 4.0,
     "fixed": {"name": "j5_out", "axis": "Z", "coord": 1626.5, "center": (-174, 0, 1626.5), "kind": "out", "fit": 112, "pcd": 100, "bolt": 5,
               "role": "на выходном валу J5 (ШМ-150, 112H7, 16xM5 D100)"},
     "load": {"name": "j6_base", "axis": "X", "coord": -73.0, "center": (-73, 0, 2617), "kind": "base", "fit": 122, "pcd": 132, "bolt": 5,
              "role": "корпус J6 (ШМ-150, 122H7, 12xM5 D132)"}},
    {"id": "LINK-6", "parts": ["LINK-6/LINK-6-01_Weldment"], "k": 6, "mesh_mm": 3.0,
     "fixed": {"name": "j6_out", "axis": "X", "coord": -14.5, "center": (-14.5, 0, 2617), "kind": "out", "fit": 112, "pcd": 100, "bolt": 5,
               "role": "на выходном валу J6 (ШМ-150, 112H7, 16xM5 D100)"},
     "load": {"name": "j7_base", "axis": "Z", "coord": 2725.0, "center": (45.5, 0, 2725), "kind": "base", "fit": 94, "pcd": 102, "bolt": 4,
              "role": "корпус J7 (ШМ-60, 94H7, 12xM4 D102)"}},
]
TOL = 0.05     # mm, geometric tolerance of the face rules
PILOT_DEPTH = 25.0


def contact_ring(itf):
    """(r_min, r_max) of the planar contact area."""
    if itf["kind"] == "out":
        return 0.0, itf["fit"] / 2.0
    if itf["kind"] == "ring":
        return 0.0, itf["r_max"]
    return itf["fit"] / 2.0, itf["pcd"] / 2.0 + 1.6 * itf["bolt"]


def selectors(itf):
    """Face rules (shared by this check and the Mechanical script)."""
    r0, r1 = contact_ring(itf)
    i = "XYZ".index(itf["axis"])
    plane = {"type": "plane", "axis": itf["axis"], "coord": itf["coord"], "center": list(itf["center"]),
             "r_min": r0, "r_max": r1}
    cyl = {"type": "cyl", "axis": itf["axis"], "center": list(itf["center"]), "radius": itf["fit"] / 2.0,
           "a_min": itf["coord"] - PILOT_DEPTH, "a_max": itf["coord"] + PILOT_DEPTH}
    return [plane, cyl] if itf["kind"] != "ring" else [plane]


# ------------------------------------------------------------------ geometry (OCC)
def read_step(path):
    from OCP.STEPControl import STEPControl_Reader
    r = STEPControl_Reader()
    r.ReadFile(path)
    r.TransferRoots()
    return r.OneShape()


def imprint(shape, itf):
    """Split the faces of the part by the contact circle (base interfaces) - the contact area becomes its
    own faces. A disk coplanar with the face is the splitting tool, the solid itself is not cut."""
    if itf["kind"] != "base":
        return shape
    from OCP.BOPAlgo import BOPAlgo_Splitter  # noqa: F401
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Splitter
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.collections import List_TopoDS_Shape as TopTools_ListOfShape
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt
    from OCP.GC import GC_MakeCircle  # noqa: F401
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.gp import gp_Circ, gp_Ax2
    i = "XYZ".index(itf["axis"])
    c = np.array(itf["center"], float)
    c[i] = itf["coord"]
    n = np.zeros(3)
    n[i] = 1
    _, r1 = contact_ring(itf)
    circ = gp_Circ(gp_Ax2(gp_Pnt(*c), gp_Dir(*n)), r1)
    wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circ).Edge()).Wire()
    disk = BRepBuilderAPI_MakeFace(gp_Pln(gp_Ax3(gp_Pnt(*c), gp_Dir(*n))), wire).Face()
    sp = BRepAlgoAPI_Splitter()
    a = TopTools_ListOfShape()
    a.Append(shape)
    t = TopTools_ListOfShape()
    t.Append(disk)
    sp.SetArguments(a)
    sp.SetTools(t)
    sp.Build()
    if not sp.IsDone():
        raise SystemExit("imprint failed")
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    ex = TopExp_Explorer(sp.Shape(), TopAbs_SOLID)
    sols = []
    while ex.More():
        sols.append(ex.Current())
        ex.Next()
    if len(sols) != 1:
        raise SystemExit(f"imprint: {len(sols)} solids (expected 1)")
    return sols[0]


def faces_of(shape):
    from OCP.BRep import BRep_Tool
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current())
        g = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, g)
        vs = []
        ev = TopExp_Explorer(f, TopAbs_VERTEX)
        while ev.More():
            p = BRep_Tool.Pnt_s(TopoDS.Vertex(ev.Current()))
            vs.append((p.X(), p.Y(), p.Z()))
            ev.Next()
        out.append({"face": f, "area": g.Mass(), "verts": np.array(vs) if vs else np.zeros((0, 3))})
        ex.Next()
    return out


def match(sel, verts, tol=TOL):
    """The rule of the Mechanical script: every vertex of the face satisfies the selector."""
    if len(verts) == 0:
        return False
    i = "XYZ".index(sel["axis"])
    c = np.array(sel["center"], float)
    d = verts - c
    ax = d[:, i]
    rad = np.sqrt(np.sum(np.delete(d, i, axis=1) ** 2, axis=1))
    if sel["type"] == "plane":
        return bool(np.all(np.abs(verts[:, i] - sel["coord"]) < tol) and np.all(rad >= sel["r_min"] - tol)
                    and np.all(rad <= sel["r_max"] + tol))
    a = verts[:, i]
    return bool(np.all(np.abs(rad - sel["radius"]) < tol) and np.all(a >= sel["a_min"] - tol)
                and np.all(a <= sel["a_max"] + tol) and (a.max() - a.min()) > 0.5)


# ------------------------------------------------------------------ loads (Pinocchio on the URDF)
class Arm:
    def __init__(self, urdf, payload, iface):
        import pinocchio as pin
        import robot_scheme as rs
        import urdf_export as ue
        self.pin = pin
        self.m = pin.buildModelFromUrdf(urdf)
        self.d = self.m.createData()
        self.m.gravity.linear[:] = [0, 0, -G]
        self.lay = rs.read_layout(os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
        rs.fk_poe(self.lay, np.zeros(7))
        groups, tool, _ = ue.build(self.lay, payload, 100.0, iface, 200.0)
        self.sub = {}            # (k, name) -> pin.Inertia in the frame of body k
        for g in range(1, 8):
            o = ue.origin_of(self.lay, g)
            acc = {}
            for (nm, _), (m, c, I) in zip(groups[g]["shapes"], groups[g]["acc"][2]):
                key = self.classify(g, nm)
                acc.setdefault(key, [0.0, np.zeros(3), []])
                ue.add_mass(acc[key], m, c, I)
            for key, a in acc.items():
                mm, com, Ic = ue.combine(a)
                self.sub[(g, key)] = (mm, com, Ic, o)
        self.origin = {g: ue.origin_of(self.lay, g) for g in range(8)}

    @staticmethod
    def classify(g, nm):
        if nm.startswith(f"L{g} "):
            return "adapter" if "Adapter" in nm else "weldment"
        j = nm.split()[0]
        if j == f"J{g + 1}":
            return "housing_next"
        return "other"

    def inertia(self, g, key):
        pin = self.pin
        if (g, key) not in self.sub:
            return pin.Inertia.Zero()
        m, com, Ic, o = self.sub[(g, key)]
        return pin.Inertia(m, (com - o) * 1e-3, Ic * 1e-6)

    def state(self, q, dq, ddq, f_tcp=None):
        """f_tcp: force [N] (world) the ARM exerts on an obstacle at the TCP (the obstacle pushes back)."""
        pin = self.pin
        if f_tcp is None:
            pin.rnea(self.m, self.d, q, dq, ddq)
        else:
            pin.forwardKinematics(self.m, self.d, q)
            pin.updateFramePlacements(self.m, self.d)
            fid = self.m.getFrameId("tcp")
            j7 = self.m.njoints - 1
            oMj = self.d.oMi[j7]
            p_loc = oMj.actInv(self.d.oMf[fid].translation)
            fl = oMj.rotation.T @ (-np.asarray(f_tcp))          # obstacle -> arm, in the J7 frame
            fext = [pin.Force.Zero() for _ in range(self.m.njoints)]
            fext[j7] = pin.Force(fl, np.cross(p_loc, fl))
            pin.rnea(self.m, self.d, q, dq, ddq, fext)
        return self.d

    def tcp_jacobian(self, q):
        pin = self.pin
        fid = self.m.getFrameId("tcp")
        pin.computeJointJacobians(self.m, self.d, q)
        pin.updateFramePlacements(self.m, self.d)
        return pin.getFrameJacobian(self.m, self.d, fid, pin.ReferenceFrame.LOCAL_WORLD_ALIGNED)[:3]

    def wrenches(self, k, part="weldment"):
        """After state(): (F_on_part_at_load, M about the frame-k origin) [N, N*m]; expected fixed reaction;
        acceleration of the part COM (m/s^2, gravity included). Frame k components = global STEP frame."""
        pin, d = self.pin, self.d
        jk = k                                   # pinocchio joint index of Jk (universe = 0)
        v, a = d.v[jk], d.a_gf[jk]
        if part == "adapter":                    # J1 adapter: only the J1 torque goes through it
            tau = d.f[jk].angular[2]
            W = pin.Force(np.zeros(3), np.array([0, 0, -tau]))     # ring -> adapter (reaction of the drive torque)
            return W, -W, np.zeros(3)
        Ih = self.inertia(k, "housing_next")
        Wd = Ih * a + v.cross(Ih * v)
        if jk + 1 < self.m.njoints:
            Wd = Wd + d.liMi[jk + 1].act(d.f[jk + 1])
        Wload = -Wd                              # housing + distal chain -> part
        Iw = self.inertia(k, part)
        Ww = Iw * a + v.cross(Iw * v)
        Wfix = Wd + Ww                           # what the fixed interface must supply (reaction)
        m, com, _, o = self.sub[(k, part)]
        r = (com - o) * 1e-3
        acc = a.linear + np.cross(a.angular, r) + np.cross(v.angular, v.linear + np.cross(v.angular, r))
        return Wload, Wfix, acc


def at_point(W, origin_mm, point_mm):
    """Force [N], moment [N*mm] about the point (both in global components)."""
    F = np.array(W.linear)
    M = np.array(W.angular) * 1e3
    r = (np.array(point_mm) - np.array(origin_mm))
    return F, M - np.cross(r, F)


def fixed_moment(arm, mdl, q, dq, ddq, f_tcp=None):
    arm.state(q, dq, ddq, f_tcp)
    k = mdl["k"]
    _, Wfix, _ = arm.wrenches(k, "adapter" if mdl.get("adapter") else "weldment")
    c = np.array(mdl["fixed"]["center"], float)
    F, M = at_point(Wfix, arm.origin[k], c)
    return np.linalg.norm(M), F, M


def worst_static(arm, mdl, rng, n=3000):
    lim = np.radians([[-180, 180], [-94, 94], [-180, 180], [-171, 171], [-180, 180], [-180, 180], [-180, 180]])
    z = np.zeros(7)
    best, bq = -1, None
    for _ in range(n):
        q = rng.uniform(lim[:, 0], lim[:, 1])
        q[0] = 0.0
        val = fixed_moment(arm, mdl, q, z, z)[0]
        if val > best:
            best, bq = val, q
    step = np.radians(10.0)
    while step > np.radians(0.2):              # coordinate refinement
        improved = False
        for i in range(1, 7):
            for s in (-1, 1):
                q = bq.copy()
                q[i] = np.clip(q[i] + s * step, lim[i, 0], lim[i, 1])
                val = fixed_moment(arm, mdl, q, z, z)[0]
                if val > best + 1e-9:
                    best, bq, improved = val, q, True
        if not improved:
            step /= 2
    return bq


def demo_traj():
    import csv
    from scipy.interpolate import CubicSpline
    with open(os.path.join(ROOT, "sim", "RTC-7", "RTC-7-demo-traj.csv"), encoding="utf-8") as f:
        r = list(csv.reader(f))
    D = np.array([[float(x) for x in row] for row in r[1:]])
    sp = CubicSpline(D[:, 0], D[:, 1:], axis=0, bc_type="not-a-knot")
    ts = np.arange(0, D[-1, 0], 1 / 250.0)
    return ts, sp(ts), sp(ts, 1), sp(ts, 2)


def contact(arm, q, tpk, mdl, n_dir=600):
    """Blocked tool at pose q: for every force direction the largest force the drives can push with
    (first joint at its peak torque, gravity included); the direction with the largest fixed moment."""
    pin = arm.pin
    z = np.zeros(7)
    g = pin.rnea(arm.m, arm.d, q, z, z).copy()
    J = arm.tcp_jacobian(q)
    best = None
    i = np.arange(n_dir) + 0.5
    phi = np.arccos(1 - 2 * i / n_dir)
    th = np.pi * (1 + 5 ** 0.5) * i
    for u in np.c_[np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)]:
        t = J.T @ u                                   # joint torque per 1 N at the TCP
        Fs = [((tpk[j] - g[j]) / t[j]) if t[j] > 1e-9 else ((tpk[j] + g[j]) / -t[j]) if t[j] < -1e-9 else np.inf
              for j in range(7)]
        F = max(0.0, min(Fs))
        jlim = int(np.argmin(Fs))
        val = fixed_moment(arm, mdl, q, z, z, F * u)[0]
        if best is None or val > best[0]:
            best = (val, F * u, jlim, F)
    return best[1], best[2], best[3]


def case(arm, mdl, name, title, q, dq, ddq, note="", f_tcp=None):
    k = mdl["k"]
    arm.state(q, dq, ddq, f_tcp)
    part = "adapter" if mdl.get("adapter") else "weldment"
    Wl, Wf, acc = arm.wrenches(k, part)
    Fl, Ml = at_point(Wl, arm.origin[k], mdl["load"]["center"])
    Ff, Mf = at_point(Wf, arm.origin[k], mdl["fixed"]["center"])
    if part == "adapter":
        acc = np.zeros(3)
    return {"name": name, "title": title, "q_deg": np.round(np.degrees(q), 2).tolist(),
            "dq_deg_s": np.round(np.degrees(dq), 2).tolist(), "ddq_deg_s2": np.round(np.degrees(ddq), 2).tolist(),
            "F_N": np.round(Fl, 2).tolist(), "M_Nmm": np.round(Ml, 0).tolist(),
            "acc_mm_s2": np.round(acc * 1e3, 1).tolist(),
            "reaction_F_N": np.round(Ff, 2).tolist(), "reaction_M_Nmm": np.round(Mf, 0).tolist(), "note": note,
            "F_tcp_N": None if f_tcp is None else np.round(f_tcp, 1).tolist()}


def picture(path, mdl, shape, sel_faces):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import robot_anim as ra
    P, I = ra.mesh(shape, 0.6, 0.4)
    T = P[I]
    fig = plt.figure(figsize=(7.5, 6.5))
    ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(Poly3DCollection(T, facecolor=(0.82, 0.84, 0.86), edgecolor="none", alpha=0.35))
    for role, col in (("fixed", (0.16, 0.37, 0.62)), ("load", (0.85, 0.39, 0.12))):
        for f in sel_faces[role]:
            Pf, If = ra.mesh(f, 0.4, 0.3)
            if len(If):
                ax.add_collection3d(Poly3DCollection(Pf[If], facecolor=col, edgecolor="none", alpha=0.95))
        c = mdl[role]["center"]
        ax.scatter([c[0]], [c[1]], [c[2]], color=col, s=40)
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    cen, span = (lo + hi) / 2, (hi - lo).max() / 2 * 1.05
    ax.set_xlim(cen[0] - span, cen[0] + span)
    ax.set_ylim(cen[1] - span, cen[1] + span)
    ax.set_zlim(cen[2] - span, cen[2] + span)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(22, -55)
    ax.set_xlabel("X, мм")
    ax.set_ylabel("Y, мм")
    ax.set_zlabel("Z, мм")
    ax.set_title(f"{mdl['id']}: синий - закрепление ({mdl['fixed']['name']}), оранжевый - нагрузка ({mdl['load']['name']})",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def reducer_card(joint):
    import joint_envelope as je
    import robot_statics as st
    jn = joint.rstrip("m")
    j = je.read_joint(os.path.join(ROOT, "joints", jn, jn + ".txt"))
    return st.card_data(os.path.join(ROOT, j["use"]["reducer"])), os.path.basename(j["use"]["reducer"]).split(".")[0]


def fmt3(v, k=1.0, nd=0):
    return " / ".join(f"{x * k:.{nd}f}" for x in v)


def write_cards(outdir, out, axes):
    """Option "a": a description of every part (markdown), plus the overview README."""
    mat = out["material"]
    rows = []
    for m in out["models"]:
        k = m["k"]
        fx, ld = m["fixed"], m["load"]
        L = [f"# {m['id']}: исходные данные для расчёта прочности (Ansys Workbench 2024 R1)", "",
             f"Деталь: {', '.join(p.split('/')[-1] for p in m['parts'])} — геометрия `{m['step']}` (одно тело, мм).", "",
             "## Материал", "",
             f"{mat['name']}: E = {mat['E_MPa'] / 1000:.1f} ГПа, ν = {mat['nu']}, ρ = {mat['rho']:.0f} кг/м³, "
             f"σ0,2 = {mat['Sy_MPa']:.0f} МПа, σв = {mat['Su_MPa']:.0f} МПа ({mat['source']}).", "",
             f"Масса детали из АМг6: **{m['mass_kg_AMg6']:.3f} кг** (в модели руки {m['mass_kg_model']:.3f} кг при 2700 кг/м³); "
             f"центр масс {fmt3(m['cog_mm'], nd=1)} мм; габарит {fmt3(m['bbox_mm'][0], nd=0)} … {fmt3(m['bbox_mm'][1], nd=0)} мм.", "",
             "## Система координат", "",
             "Глобальная СК файла STEP = СК руки в нулевой позе (рука вытянута вверх): начало на оси J1 на верхнем торце ОПУ, "
             "Z вверх по оси J1, X — в сторону колонны J3. Все силы, моменты и ускорения ниже — в этой СК, мм / Н / Н·мм. "
             "Поза руки в каждом случае своя, поэтому направление веса в СК детали меняется от случая к случаю.", "",
             f"![Интерфейсы](../pictures/{m['id']}.png)", "",
             "## Закрепление (Fixed Support)", "",
             f"**{fx['name']}** — {fx['role']}. Центр интерфейса {fmt3(fx['center'], nd=1)} мм.", ""]
        for sel in fx["selectors"]:
            L.append("- " + sel_text(sel))
        L += [f"- площадь выбранных граней {fx['area_mm2']:.0f} мм² ({fx['n_faces']} гр.)", "",
              "Болты и швы не моделируются: грани закрепляются жёстко (болтовой стык = сплошной).", "",
              "## Нагрузка (Remote Force + Moment через удалённую точку, поведение Rigid)", "",
              f"**{ld['name']}** — {ld['role']}. Удалённая точка: **{fmt3(ld['center'], nd=1)} мм**.", ""]
        for sel in ld["selectors"]:
            L.append("- " + sel_text(sel))
        L += [f"- площадь выбранных граней {ld['area_mm2']:.0f} мм² ({ld['n_faces']} гр.)", "",
              "Плюс поле ускорений самой детали (Acceleration, компоненты ниже; это ускорение тела, вес включён: "
              "при покое оно равно +9807 мм/с² «вверх» в СК детали).", "",
              "## Расчётные случаи", "",
              "| Случай | Сила на детали Fx / Fy / Fz, Н | Момент Mx / My / Mz, Н·м (в удалённой точке) | Ускорение детали ax / ay / az, мм/с² | Ожидаемая реакция в закреплении: F, Н; M, Н·м (в центре закрепления) | Требуемый запас / допускаемое σэкв |",
              "|---|---|---|---|---|---|"]
        for c in m["cases"]:
            L.append(f"| **{c['name']}** {c['title']} | {fmt3(c['F_N'])} | {fmt3(c['M_Nmm'], 1e-3)} | {fmt3(c['acc_mm_s2'])} | "
                     f"F {fmt3(c['reaction_F_N'])}; M {fmt3(c['reaction_M_Nmm'], 1e-3)} | {c['sf_required']:g} / "
                     f"{c['sigma_allow_MPa']:.0f} МПа (у швов ×{mat['weld_factor']}: {c['sigma_allow_MPa'] * mat['weld_factor']:.0f}) |")
        L += ["", "Позы и примечания:", ""]
        for c in m["cases"]:
            extra = f"; сила на инструменте {fmt3(c['F_tcp_N'])} Н" if c.get("F_tcp_N") else ""
            L.append(f"- **{c['name']}**: q = {', '.join(f'{v:g}' for v in c['q_deg'])}° — {c['note']}{extra}")
        # reducer output bearing (the fixed interface is a joint output)
        if fx["name"].endswith("_out"):            # (J1: the ОПУ takes the tilt, the adapter only the torque)
            ax = axes[k - 1]
            rd, rn = reducer_card(ax["joint"])
            i = "XYZ".index(fx["selectors"][0]["axis"])
            L += ["", f"## Выходной подшипник редуктора J{k} ({rn})", "",
                  f"Реакция в закреплении = нагрузка на выходной вал J{k}. Каталог: опрокидывающий момент M_tilt = "
                  f"{rd.get('M_tilt', '?')} Н·м, осевая сила F_axial = {rd.get('F_axial', '?')} Н.", "",
                  "| Случай | Крутящий, Н·м | Опрокидывающий, Н·м | % M_tilt | Осевая сила, Н |", "|---|---|---|---|---|"]
            for c in m["cases"]:
                M = np.array(c["reaction_model_M_Nmm"]) / 1e3     # the real link (model mass)
                F = np.array(c["reaction_model_F_N"])
                tilt = float(np.linalg.norm(np.delete(M, i)))
                mt = float(rd["M_tilt"]) if "M_tilt" in rd else float("nan")
                L.append(f"| {c['name']} | {abs(M[i]):.0f} | {tilt:.0f} | {100 * tilt / mt:.0f} % | {abs(F[i]):.0f} |")
                rows.append((m["id"], c["name"], k, rn, tilt, mt))
        L += ["", "## Как задать в Workbench вручную", "",
              "1. Static Structural, материал АМг6 (свойства выше), геометрия — STEP, единицы мм.",
              "2. Закрепление: Fixed Support на гранях закрепления.",
              f"3. Remote Point в {fmt3(ld['center'], nd=1)} мм на гранях нагрузки, Behavior = Rigid.",
              "4. На эту удалённую точку — Remote Force (компоненты) и Moment (компоненты) случая; Acceleration — компоненты случая.",
              f"5. Сетка: тетраэдры 2-го порядка, размер {m['mesh_mm']:g} мм (у швов и галтелей — сгустить).",
              "6. Проверка: реакция Fixed Support (Force/Moment Reaction в центре закрепления) должна совпасть с колонкой "
              "«Ожидаемая реакция» с точностью до погрешности сетки — так видно, что нагрузки заданы верно.",
              "7. Критерий: σэкв (Мизес) ≤ допускаемого; локальные пики на кромках закрепления — концентрация от жёсткой заделки, "
              "их не учитывать (оценивать на расстоянии 1–2 элементов от кромки).", ""]
        open(os.path.join(outdir, "cards", m["id"] + ".md"), "w", encoding="utf-8").write("\n".join(L))
    return rows


def write_readme(outdir, out, tilt):
    mat = out["material"]
    L = ["# RTC-7: исходные данные для расчёта прочности звеньев в Ansys Workbench 2024 R1", "",
         "Сгенерировано `python tools/fea_export.py` из тех же описаний, что модель SolidWorks, Simscape и анимация.", "",
         "## Состав", "",
         "| Файл | Что это |", "|---|---|",
         "| `geometry/<звено>.step` | деталь в глобальной СК руки (нулевая поза, мм), зоны контакта интерфейсов выделены в отдельные грани |",
         "| `cards/<звено>.md` | вариант «а»: описание детали — материал, СК, закрепление, нагрузка, случаи, проверка реакции, подшипник редуктора |",
         "| `pictures/<звено>.png` | грани закрепления (синие) и нагрузки (оранжевые) |",
         "| `rtc7_fea.json` | все данные для скриптов (правила выбора граней, нагрузки, ожидаемые реакции) |",
         "| `ansys/rtc7_wb.py` | вариант «б»: скрипт Workbench — проект со всеми звеньями, материал, геометрия, запуск скрипта Mechanical |",
         "| `ansys/rtc7_mech.py` | скрипт Mechanical — грани, закрепление, удалённая точка, силы/моменты/ускорения по шагам, сетка, результаты, расчёт |",
         "| `ccx/summary.md` | предварительный расчёт здесь же (CalculiX) по тем же данным — ориентир до Ansys |", "",
         "## Как запустить (вариант «б»)", "",
         "1. Распакуйте папку `RTC-7` целиком (например `C:\\rtc\\fea\\RTC-7`).",
         "2. Workbench 2024 R1: File → Scripting → Run Script File… → `ansys\\rtc7_wb.py`.",
         "   Создаются системы Static Structural LINK-1 … LINK-6, LINK-1A, в каждой материал АМг6 и геометрия; по очереди "
         "открывается Mechanical, скрипт строит постановку и решает (в начале `rtc7_wb.py`: `ONLY = [\"LINK-3\"]` — только одно звено, "
         "`SOLVE = False` — без решения).",
         "3. Результаты: `results_<звено>.csv` (σэкв max, допускаемое, запас, реакция: расчёт / ожидаемая) и `log_<звено>.txt` рядом с `rtc7_fea.json`; "
         "проект `RTC7_links.wbpj`.",
         "4. Если что-то не создалось автоматически (имена вызовов API немного отличаются между версиями) — скрипт пишет предупреждение; "
         "Mechanical-часть можно запустить вручную: Automation → Scripting → `rtc7_mech.py` (в начале указать `CONFIG`). "
         "Пришлите текст ошибки — поправлю, как с макросом SolidWorks.", "",
         "Вручную (вариант «а») — по карточкам `cards/*.md`, там же порядок действий.", "",
         "## Постановка", "",
         f"- Материал {mat['name']}: E {mat['E_MPa'] / 1000:.1f} ГПа, ν {mat['nu']}, ρ {mat['rho']:.0f} кг/м³, σ0,2 {mat['Sy_MPa']:.0f} МПа, "
         f"σв {mat['Su_MPa']:.0f} МПа. {mat['source']}.",
         f"- Требуемый запас по σ0,2: {out['safety_factor']:g} в рабочих случаях S и D, {out['safety_factor_C']:g} в предельном C; у сварных швов "
         f"допускаемое ×{mat['weld_factor']} (принято).",
         "- Звено — одно тело (болты и швы не моделируются): грани закрепления жёстко закреплены, грани нагрузки жёстко связаны с удалённой точкой "
         "в центре интерфейса; на неё — сила и момент от корпуса следующего шарнира (= всё, что дальше по руке, плюс вес и инерция этого корпуса).",
         "- Вес и ускорение самой детали — полем ускорений (Acceleration). Собственное вращение детали (центробежные силы) учтено только через ускорение "
         "центра масс — вклад мал.",
         f"- Груз {out['payload_kg']:g} кг (центр масс в 100 мм от фланца) + интерфейс смены инструмента {out['iface_kg']:g} кг; массы и инерции — модель руки "
         "`sim/RTC-7/RTC-7.urdf` (масса DMRD-80E оценочная).", "",
         "Случаи:", "",
         "- **S** — статика: поза руки с наибольшим моментом в закреплении звена (поиск по J2…J7 в пределах ходов).",
         "- **D** — демо-программа с ускорениями: момент наибольший при выходе на максимальный вылет.",
         "- **C** — упор инструмента (столкновение / аварийная ситуация): в позе S инструмент упёрся, приводы давят до пикового момента редуктора "
         "в первом же шарнире; направление силы — худшее для звена. Вместо «торможения пиковым моментом» как жёсткого тела: для кистевых осей оно "
         "даёт нереальные замедления (сотни–тысячи рад/с²) и абсурдные нагрузки.", "",
         "## Нагрузки (модуль силы и момента в удалённой точке)", "",
         "| Звено | Закрепление | Нагрузка | S: F, Н / M, Н·м | D: F, Н / M, Н·м | C: F, Н / M, Н·м |", "|---|---|---|---|---|---|"]
    for m in out["models"]:
        cs = {c["name"]: c for c in m["cases"]}
        cell = lambda n: (f"{np.linalg.norm(cs[n]['F_N']):.0f} / {np.linalg.norm(cs[n]['M_Nmm']) / 1e3:.0f}" if n in cs else "—")
        L.append(f"| {m['id']} | {m['fixed']['name']} | {m['load']['name']} | {cell('S')} | {cell('D')} | {cell('C')} |")
    L += ["", "## Попутно: выходные подшипники редукторов", "",
          "Реакция в закреплении звена — это нагрузка на выходной вал шарнира, на котором звено стоит. Сравнение опрокидывающего момента "
          "с каталожным M_tilt:", "", "| Звено | Шарнир | Редуктор | S, % M_tilt | D, % M_tilt | C, % M_tilt |", "|---|---|---|---|---|---|"]
    by = {}
    for mid, cn, k, rn, t, mt in tilt:
        by.setdefault((mid, k, rn, mt), {})[cn] = t
    for (mid, k, rn, mt), d in by.items():
        f = lambda n: (f"{d[n]:.0f} Н·м ({100 * d[n] / mt:.0f} %)" if n in d else "—")
        L.append(f"| {mid} | J{k} | {rn} (M_tilt {mt:.0f}) | {f('S')} | {f('D')} | {f('C')} |")
    L += ["", "В рабочих случаях выход J3 (KB45) перегружен по опрокидывающему моменту, J5 (KB32) — на пределе: это вопрос выбора "
          "редукторов / разгрузки плеча, а не прочности звеньев. Случай C превышает M_tilt всех редукторов — его на практике ограничивает "
          "контроль моментов (обнаружение столкновения).", ""]
    open(os.path.join(outdir, "README.md"), "w", encoding="utf-8").write("\n".join(L))


def sel_text(sel):
    i = sel["axis"]
    if sel["type"] == "plane":
        return (f"плоские грани в плоскости {i} = {sel['coord']:g} мм, все вершины на расстоянии {sel['r_min']:g}…{sel['r_max']:g} мм "
                f"от оси шарнира (ось ∥ {i} через {fmt3(sel['center'], nd=1)})")
    return (f"посадочный цилиндр R {sel['radius']:g} мм соосно оси шарнира, по оси {i} в пределах "
            f"{sel['a_min']:g}…{sel['a_max']:g} мм")


def write_step(shape, path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    w = STEPControl_Writer()
    w.Transfer(shape, STEPControl_AsIs)
    if w.Write(path) != IFSelect_RetDone:
        raise SystemExit("STEP write failed: " + path)


def main():
    import link_build as lb
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "fea", "RTC-7"))
    ap.add_argument("--urdf", default=os.path.join(ROOT, "sim", "RTC-7", "RTC-7.urdf"))
    ap.add_argument("--payload", type=float, default=8.0)
    ap.add_argument("--iface", type=float, default=4.0)
    ap.add_argument("--sf", type=float, default=1.5, help="required safety factor to the yield, cases S and D")
    ap.add_argument("--sf-c", type=float, default=1.0, help="required safety factor to the yield, case C (accidental)")
    ap.add_argument("--only", help="comma list of model ids")
    a = ap.parse_args()
    for sub in ("geometry", "cards", "pictures"):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    arm = Arm(a.urdf, a.payload, a.iface)
    rng = np.random.default_rng(7)
    ts, Q, DQ, DDQ = demo_traj()
    axes = arm.lay["axes"]
    out = {"material": MAT, "safety_factor": a.sf, "safety_factor_C": a.sf_c, "payload_kg": a.payload, "iface_kg": a.iface,
           "units": {"length": "mm", "force": "N", "moment": "N*mm", "acceleration": "mm/s^2"},
           "tolerance_mm": TOL, "models": []}
    for mdl in MODELS:
        if a.only and mdl["id"] not in a.only.split(","):
            continue
        k = mdl["k"]
        # --- geometry: union of the parts, imprint of both interfaces, selection check
        shapes = [read_step(os.path.join(ROOT, "links", p + ".step")) for p in mdl["parts"]]
        shape = shapes[0]
        for role in ("fixed", "load"):
            shape = imprint(shape, mdl[role])
        F = faces_of(shape)
        sel_info, sel_faces = {}, {}
        for role in ("fixed", "load"):
            sels = selectors(mdl[role])
            hit = [f for f in F if any(match(s, f["verts"]) for s in sels)]
            sel_faces[role] = [f["face"] for f in hit]
            per = {s["type"]: round(sum(f["area"] for f in F if match(s, f["verts"])), 1) for s in sels}
            sel_info[role] = {"selectors": sels, "n_faces": len(hit), "area_mm2": round(sum(f["area"] for f in hit), 1),
                              "area_by_type_mm2": per}
            if not hit or any(v <= 0 for v in per.values()):
                raise SystemExit(f"{mdl['id']} {role}: selection empty {per}")
        step = os.path.join(a.out, "geometry", mdl["id"] + ".step")
        write_step(shape, step)
        v, cg = lb.volume(shape)
        allv = np.concatenate([f["verts"] for f in F if len(f["verts"])])
        picture(os.path.join(a.out, "pictures", mdl["id"] + ".png"), mdl, shape, sel_faces)
        # --- load cases
        part = "adapter" if mdl.get("adapter") else "weldment"
        z = np.zeros(7)
        cases = []
        jn, jn1 = axes[k - 1]["joint"], axes[k]["joint"] if k < 7 else None
        if part == "adapter":
            Mz = [abs(arm.state(Q[i], DQ[i], DDQ[i]).f[1].angular[2]) for i in range(len(ts))]
            i = int(np.argmax(Mz))
            cases.append(case(arm, mdl, "D", "демо-программа: наибольший момент J1", Q[i], DQ[i], DDQ[i], f"t = {ts[i]:.2f} с"))
            qS = np.radians([0, 90, 0, 0, 0, 0, 0])
            tcp = arm.tcp_jacobian(qS)
            # J1 at its peak torque: horizontal force at the TCP, lever = TCP distance from the J1 axis
            arm.pin.forwardKinematics(arm.m, arm.d, qS)
            arm.pin.updateFramePlacements(arm.m, arm.d)
            p = arm.d.oMf[arm.m.getFrameId("tcp")].translation
            u = np.cross([0, 0, 1.0], p)
            u /= np.linalg.norm(u)
            F = T_PEAK[jn] / np.linalg.norm(p[:2])
            cases.append(case(arm, mdl, "C", f"упор: J1 развивает пиковый момент редуктора {T_PEAK[jn]:.0f} Н·м", qS, z, z,
                              f"рука горизонтально, сила на инструменте {F:.0f} Н", F * u))
        else:
            qS = worst_static(arm, mdl, rng)
            cases.append(case(arm, mdl, "S", "статика: худшая поза (наибольший момент в закреплении)", qS, z, z,
                              f"груз {a.payload:g} кг + интерфейс {a.iface:g} кг"))
            mm = [fixed_moment(arm, mdl, Q[i], DQ[i], DDQ[i])[0] for i in range(len(ts))]
            i = int(np.argmax(mm))
            cases.append(case(arm, mdl, "D", "демо-программа: наибольший момент в закреплении", Q[i], DQ[i], DDQ[i],
                              f"t = {ts[i]:.2f} с"))
            tpk = [T_PEAK[ax["joint"]] for ax in axes]
            fv, jlim, F = contact(arm, qS, tpk, mdl)
            cases.append(case(arm, mdl, "C", "упор инструмента: приводы до пикового момента редуктора",
                              qS, z, z, f"поза S, сила на инструменте {F:.0f} Н (ограничивает J{jlim + 1}, "
                              f"{tpk[jlim]:.0f} Н·м)", fv))
        # expected reaction exactly as Ansys will give it: equilibrium of the part with the AMg6 mass
        # (the acceleration field acts on the COM of the STEP solid; own rotation of the part neglected)
        m_ans = v * MAT["rho"] * 1e-9
        cog = np.array([cg.X(), cg.Y(), cg.Z()])
        C0 = np.array(mdl["fixed"]["center"], float)
        P = np.array(mdl["load"]["center"], float)
        for c in cases:
            Fl, Ml, A = np.array(c["F_N"]), np.array(c["M_Nmm"]), np.array(c["acc_mm_s2"]) * 1e-3
            mA = m_ans * A                                  # N
            Ff = mA - Fl
            Mf = np.cross(cog - C0, mA) - (Ml + np.cross(P - C0, Fl))
            c["reaction_model_F_N"], c["reaction_model_M_Nmm"] = c["reaction_F_N"], c["reaction_M_Nmm"]
            c["reaction_F_N"], c["reaction_M_Nmm"] = np.round(Ff, 2).tolist(), np.round(Mf, 0).tolist()
        for c in cases:
            c["sf_required"] = a.sf_c if c["name"] == "C" else a.sf
            c["sigma_allow_MPa"] = round(MAT["Sy_MPa"] / c["sf_required"], 1)
        m_part = arm.sub[(k, part)][0]
        out["models"].append({"id": mdl["id"], "k": k, "step": "geometry/" + mdl["id"] + ".step",
                              "parts": mdl["parts"], "mesh_mm": mdl["mesh_mm"],
                              "volume_mm3": round(v, 0), "mass_kg_AMg6": round(v * MAT["rho"] * 1e-9, 3),
                              "mass_kg_model": round(m_part, 3),
                              "cog_mm": [round(cg.X(), 2), round(cg.Y(), 2), round(cg.Z(), 2)],
                              "bbox_mm": [np.round(allv.min(0), 2).tolist(), np.round(allv.max(0), 2).tolist()],
                              "fixed": dict(name=mdl["fixed"]["name"], role=mdl["fixed"]["role"],
                                            center=list(mdl["fixed"]["center"]), **sel_info["fixed"]),
                              "load": dict(name=mdl["load"]["name"], role=mdl["load"]["role"],
                                           center=list(mdl["load"]["center"]), **sel_info["load"]),
                              "cases": cases})
        print(f"{mdl['id']}: fixed {sel_info['fixed']['area_by_type_mm2']}, load {sel_info['load']['area_by_type_mm2']}, "
              f"{len(cases)} cases")
        for c in cases:
            print(f"   {c['name']:3s} |F| {np.linalg.norm(c['F_N']):8.0f} N  |M| {np.linalg.norm(c['M_Nmm']) / 1e3:7.0f} N*m  "
                  f"reaction |M| {np.linalg.norm(c['reaction_M_Nmm']) / 1e3:7.0f} N*m")
    with open(os.path.join(a.out, "rtc7_fea.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    tilt = write_cards(a.out, out, axes)
    write_readme(a.out, out, tilt)
    print("->", os.path.join(a.out, "rtc7_fea.json"))


if __name__ == "__main__":
    main()
