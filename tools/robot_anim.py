#!/usr/bin/env python3
"""Motion animation of the arm: program -> joint trajectory -> viewer HTML / SolidWorks frames / checks.

    python tools/robot_anim.py [--program robot/RTC-7-demo.txt] [--check 3]
                               [--html robot/anim/RTC-7-viewer.html] [--sw robot/RTC-7-anim.txt --sw-step 2]
                               [--csv robot/anim/RTC-7-demo.csv]

* program (robot/RTC-7-demo.txt): MOVEJ / MOVEL / WAIT / LABEL lines, see the file header;
  MOVEJ - quintic blend in joint space, MOVEL - straight TCP line with the orientation kept
  (damped least squares IK on the exact axis model, 7 joints -> the redundancy keeps the pose
  close to the previous one);
* geometry for the viewer: the designed links (links/LINK-n, OpenCascade solids of the specs),
  the joints as revolved solids of their real part profiles (+ motor and sensor-cover envelopes),
  the ОПУ rings and an ASSUMED tool (tool-change interface + gripper) -> triangle meshes;
* --check N: every N-th frame the bodies of non-neighbouring links are intersected (OCC),
  and the tool is kept above the ОПУ face;
* --sw: ROBOTANIM spec for BuildFromSpec (SolidWorks): the components of the arm assembly and
  their frames per animation frame -> the macro moves them and saves the pictures;
* the viewer also gets the mass model (tools/robot_statics.py) -> live gravity torques.
"""
import argparse
import base64
import json
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_envelope as je  # noqa: E402
import link_build as lb  # noqa: E402
import robot_scheme as rs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMITS = [(-180, 180), (-94, 94), (-180, 180), (-171, 171), (-180, 180), (-180, 180), (-180, 180)]

# viewer colours (presentation palette; SolidWorks keeps its own)
COL = {"link": "#e7e3da", "housing": "#3d434b", "output": "#a9b1ba", "motorhousing": "#c9cfd6",
       "motor": "#25282c", "cover": "#2f3338", "clamp": "#8f98a3", "opu": "#7d858f", "opu_in": "#a9b1ba",
       "tool": "#e8742f", "gripper": "#3d434b", "rot": "#8f98a3"}


# ------------------------------------------------------------------ program -> trajectory
def read_program(path):
    prg = {"fps": 30, "tool": 200.0, "start": [0.0] * 7, "steps": [], "name": "?"}
    for raw in open(path, encoding="utf-8"):
        t = re.split(r"#", raw, maxsplit=1)[0].split()
        if not t:
            continue
        k = t[0].upper()
        if k == "PROGRAM":
            prg["name"] = t[1]
        elif k == "FPS":
            prg["fps"] = int(t[1])
        elif k == "TOOL":
            prg["tool"] = float(t[1])
        elif k == "START":
            prg["start"] = [float(v) for v in t[1:8]]
        elif k == "LABEL":
            prg["steps"].append(("LABEL", raw.split(None, 1)[1].split("#")[0].strip()))
        elif k in ("GRIP", "RELEASE"):
            prg["steps"].append((k,))
        elif k in ("MOVEJ", "MOVEL", "WAIT"):
            prg["steps"].append((k, float(t[1]), [float(v) for v in t[2:]]))
    return prg


def s_curve(n):
    """Quintic time scaling, n samples from 0 (excl.) to 1 (incl.)."""
    t = np.arange(1, n + 1) / n
    return 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5


def tcp_T(lay, q, tool):
    _, _, F = rs.fk_poe(lay, q)
    T = F.copy()
    T[:3, 3] = F[:3, 3] + F[:3, 2] * tool
    return T


def jacobian(lay, q, tool, h=1e-6):
    T0 = tcp_T(lay, q, tool)
    J = np.zeros((6, len(q)))
    for i in range(len(q)):
        dq = q.copy()
        dq[i] += h
        T1 = tcp_T(lay, dq, tool)
        J[:3, i] = (T1[:3, 3] - T0[:3, 3]) / h
        dR = T1[:3, :3] @ T0[:3, :3].T
        J[3:, i] = np.array([dR[2, 1] - dR[1, 2], dR[0, 2] - dR[2, 0], dR[1, 0] - dR[0, 1]]) / (2 * h)
    return J, T0


def ik_step(lay, q, target, tool, iters=30):
    """Damped least squares to the target TCP frame, from q (rad)."""
    q = q.copy()
    for _ in range(iters):
        J, T = jacobian(lay, q, tool)
        e = np.zeros(6)
        e[:3] = target[:3, 3] - T[:3, 3]
        dR = target[:3, :3] @ T[:3, :3].T
        e[3:] = 0.5 * np.array([dR[2, 1] - dR[1, 2], dR[0, 2] - dR[2, 0], dR[1, 0] - dR[0, 1]]) * 500.0
        if np.linalg.norm(e[:3]) < 0.01 and np.linalg.norm(e[3:]) < 0.005:
            break
        W = np.diag([1, 1, 1, 500, 500, 500.0])
        Jw = W @ J
        ew = W @ np.r_[e[:3], e[3:] / 500.0]
        lam = 5.0
        q += Jw.T @ np.linalg.solve(Jw @ Jw.T + lam ** 2 * np.eye(6), ew)
    return q


def trajectory(lay, prg):
    fps = prg["fps"]
    q = np.radians(prg["start"])
    frames, labels, label = [q.copy()], [], ""
    labels.append((0, ""))
    events = []
    for st in prg["steps"]:
        if st[0] == "LABEL":
            labels.append((len(frames) - 1, st[1]))
            continue
        if st[0] in ("GRIP", "RELEASE"):
            T = tcp_T(lay, q, prg["tool"])
            events.append({"kind": st[0], "frame": len(frames) - 1, "T": np.round(T, 4).tolist()})
            continue
        kind, dur, args = st
        n = max(1, int(round(dur * fps)))
        if kind == "WAIT":
            frames += [q.copy()] * n
        elif kind == "MOVEJ":
            q1 = np.radians(args[:7])
            for s in s_curve(n):
                frames.append(q + (q1 - q) * s)
            q = q1
        elif kind == "MOVEL":
            T0 = tcp_T(lay, q, prg["tool"])
            d = np.array(args[:3])
            for s in s_curve(n):
                T = T0.copy()
                T[:3, 3] = T0[:3, 3] + d * s
                q = ik_step(lay, q, T, prg["tool"])
                frames.append(q.copy())
            err = np.linalg.norm(tcp_T(lay, q, prg["tool"])[:3, 3] - (T0[:3, 3] + d))
            if err > 0.5:
                print(f"WARNING MOVEL {d}: end error {err:.2f} mm")
    prg["events"] = events
    return np.array(frames), labels


# ------------------------------------------------------------------ geometry
def group_T(lay, q, k):
    """World transform of the bodies of link k (moved by joints 1..k)."""
    T = np.eye(4)
    for a, qi in list(zip(lay["axes"], q))[:k]:
        T = T @ rs.screw_T(a["w"], a["p"], qi)
    return T


def colour_of(name, kind):
    n = name.lower()
    if kind == "cover":
        return COL["cover"]
    if kind == "motor":
        return COL["motor"]
    if "motorhousing" in n or "adapterplate" in n:
        return COL["motorhousing"]
    if "outputshaft" in n:
        return COL["output"]
    if "housing" in n:
        return COL["housing"]
    if "clamp" in n:
        return COL["clamp"]
    return COL["rot"]


def bodies(lay, tool_len):
    """[(name, group, colour, OCC shape)] at the zero pose."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    env = je.all_joints()
    out = []
    names = [a["name"] for a in lay["axes"]]
    for k in range(1, len(names)):
        spec = os.path.join(ROOT, "links", f"LINK-{k}", f"LINK-{k}.txt")
        if os.path.isfile(spec):
            for p in lb.parse(spec)[0]:
                out.append((f"L{k} {p['name']}", k, COL["link"], lb.build_part(p)))
    for i, a in enumerate(lay["axes"]):
        e = env.get(a["joint"]) or env.get(a["joint"].rstrip("m"))
        md = np.zeros(3)
        md["XYZ".index(a["motor"][1])] = 1 if a["motor"][0] == "+" else -1
        u = -md
        origin = a["face"] - u * e["x_out"]
        for nm, kind, pts in e["profiles"]:
            g = i + 1 if nm.endswith("OutputShaft") else i     # housing side stays on the previous link
            out.append((f"{a['name']} {nm}", g, colour_of(nm, kind), lb.revolved(origin, u, pts)))
    z0 = np.array([0, 0, -28.0])
    zz = np.array([0, 0, 1.0])
    out.append(("ОПУ outer ring", 0, COL["opu"], lb.revolved(z0, zz, [(0, 89.5), (28, 89.5), (28, 120), (0, 120)])))
    out.append(("ОПУ inner ring", 1, COL["opu_in"], lb.revolved(z0, zz, [(0, 57.5), (28, 57.5), (28, 88.5), (0, 88.5)])))
    # ASSUMED tool: tool-change interface D100 x 45 + gripper body + 2 fingers, TCP at tool_len
    f = lay["flange"]
    p, w = f["p"], f["w"]
    n = len(lay["axes"])
    out.append(("tool-change interface (assumed)", n, COL["tool"],
                lb.revolved(p, w, [(0, 0), (45, 0), (45, 50), (38, 50), (38, 44), (0, 44)])))
    gz = p[2] + 45
    out.append(("gripper body (assumed)", n, COL["gripper"],
                BRepPrimAPI_MakeBox(gp_Pnt(p[0] - 70, p[1] - 40, gz), 140, 80, 85).Shape()))
    for sx in (-1, 1):
        x0 = p[0] + sx * 48 - 9
        out.append((f"gripper finger {'+' if sx > 0 else '-'} (assumed)", n, COL["tool"],
                    BRepPrimAPI_MakeBox(gp_Pnt(x0, p[1] - 14, gz + 85), 18, 28, tool_len - 130).Shape()))
    return out


def mesh(shape, defl=0.5, ang=0.35):
    """Indexed triangle mesh (float32 positions, uint32 indices) of an OCC shape, outward winding."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    BRepMesh_IncrementalMesh(shape, defl, False, ang, True)
    P, I, base = [], [], 0
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current())
        loc = TopLoc_Location()
        tr = BRep_Tool.Triangulation_s(f, loc)
        if tr is not None:
            T = loc.Transformation()
            for i in range(1, tr.NbNodes() + 1):
                q = tr.Node(i).Transformed(T)
                P.append((q.X(), q.Y(), q.Z()))
            rev = f.Orientation() == TopAbs_REVERSED
            for i in range(1, tr.NbTriangles() + 1):
                a, b, c = tr.Triangle(i).Get()
                I.append((base + a - 1, base + c - 1, base + b - 1) if rev else (base + a - 1, base + b - 1, base + c - 1))
            base += tr.NbNodes()
        ex.Next()
    return np.array(P, np.float32), np.array(I, np.uint32)


# ------------------------------------------------------------------ checks
def check_frames(lay, frames, bl, every, tool):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.Bnd import Bnd_Box
    from OCP.gp import gp_Trsf

    def trsf(T):
        t = gp_Trsf()
        t.SetValues(*T[0, :4], *T[1, :4], *T[2, :4])
        return t

    bad = []
    for fi in range(0, len(frames), every):
        q = frames[fi]
        moved = []
        for nm, g, c, s in bl:
            s2 = BRepBuilderAPI_Transform(s, trsf(group_T(lay, q, g)), True).Shape()
            b = Bnd_Box()
            BRepBndLib.Add_s(s2, b)
            moved.append((nm, g, s2, b))
        for i in range(len(moved)):
            for j in range(i + 1, len(moved)):
                ni, gi, si, bi = moved[i]
                nj, gj, sj, bj = moved[j]
                if abs(gi - gj) < 2 or bi.IsOut(bj):
                    continue
                v, _ = lb.volume(BRepAlgoAPI_Common(si, sj).Shape())
                if v > 1.0:
                    bad.append((fi, ni, nj, v))
        tz = tcp_T(lay, q, tool)[2, 3]
        zmin = min(m[3].CornerMin().Z() for m in moved if m[1] >= 3)
        if zmin < 0:
            bad.append((fi, "arm below the ОПУ face", f"z min {zmin:.0f}", 0))
    return bad


# ------------------------------------------------------------------ outputs
def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def statics_data(lay, tool):
    import robot_statics as st
    b0, _ = st.bodies(lay, 0.0, 100.0)
    rated = []
    for a in lay["axes"]:
        j = je.read_joint(os.path.join(ROOT, "joints", a["joint"].rstrip("m"), a["joint"].rstrip("m") + ".txt"))
        rd = st.card_data(os.path.join(ROOT, j["use"]["reducer"]))
        rated.append(float(rd.get("T_design", rd["T_rated"])))
    return {"bodies": [[round(m, 3), [round(float(v), 1) for v in p], k] for m, p, k, _ in b0],
            "rated": rated, "payload_com": 100.0}


def write_html(path, scene):
    tpl = open(os.path.join(ROOT, "tools", "anim_viewer.html"), encoding="utf-8").read()
    html = tpl.replace("/*SCENE_JSON*/null", json.dumps(scene, ensure_ascii=False, separators=(",", ":")))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(html)
    print(f"viewer -> {path} ({os.path.getsize(path) / 1e6:.1f} MB)")


def write_sw(path, lay, frames, step, asm_spec):
    """ROBOTANIM spec: the COMP lines of the arm assembly + their frames for every step-th frame."""
    comps = []
    for raw in open(asm_spec, encoding="utf-8"):
        t = re.split(r"#", raw, maxsplit=1)[0].split()
        if t and t[0] == "COMP":
            comps.append(t)
    def grp(nm):
        if nm == "OPU":
            return 0
        if nm.startswith("L"):
            return int(nm[1:])
        return int(nm[1:]) - 1          # joint n sits on link n-1
    name = os.path.splitext(os.path.basename(path))[0]
    L = [f"# Animation of the arm in SolidWorks - GENERATED by tools/robot_anim.py (components of {os.path.basename(asm_spec)})",
         "# Run BuildFromSpec on this file: the models of the arm assembly are inserted without mates",
         "# (rigid, floating), then for every FRAME the components are moved to their frames, the view",
         "# is redrawn and (IMAGES) saved as a picture into the folder <name>-frames next to this file.",
         "# Join the pictures into a video e.g. with ffmpeg:  ffmpeg -framerate 15 -i f%04d.jpg -pix_fmt yuv420p anim.mp4",
         f"ROBOTANIM {name}", "REBUILD no", "IMAGES jpg        # jpg | png | bmp | none (only play on the screen)",
         "VIEW   *Isometric  # named view used for every frame", ""]
    L += [" ".join(t) for t in comps]
    L.append("")
    for fi in range(0, len(frames), step):
        L.append(f"FRAME {fi // step}")
        for t in comps:
            o = np.array([float(v) for v in t[3:6]])
            x = np.array([float(v) for v in t[6:9]])
            z = np.array([float(v) for v in t[9:12]])
            T = group_T(lay, frames[fi], grp(t[1]))
            R = T[:3, :3]
            o2, x2, z2 = R @ o + T[:3, 3], R @ x, R @ z
            L.append("P " + t[1] + " " + " ".join(f"{v:.2f}" for v in o2) + "  " +
                     " ".join(f"{v:.5f}" for v in x2) + "  " + " ".join(f"{v:.5f}" for v in z2))
    L.append("END")
    open(path, "w", encoding="utf-8", newline="\r\n").write("\n".join(L) + "\n")
    print(f"SolidWorks animation -> {path}: {len(range(0, len(frames), step))} frames x {len(comps)} components")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    ap.add_argument("--program", default=os.path.join(ROOT, "robot", "RTC-7-demo.txt"))
    ap.add_argument("--html")
    ap.add_argument("--sw")
    ap.add_argument("--sw-step", type=int, default=2, help="every n-th frame to SolidWorks")
    ap.add_argument("--asm", default=os.path.join(ROOT, "robot", "RTC-7-J1-J7.txt"))
    ap.add_argument("--check", type=int, default=0, help="check every n-th frame for contacts")
    ap.add_argument("--csv")
    a = ap.parse_args()
    lay = rs.read_layout(a.layout)
    prg = read_program(a.program)
    frames, labels = trajectory(lay, prg)
    deg = np.degrees(frames)
    print(f"program {prg['name']}: {len(frames)} frames, {len(frames) / prg['fps']:.1f} s at {prg['fps']} fps")
    for i, (lo, hi) in enumerate(LIMITS):
        if deg[:, i].min() < lo - 1e-6 or deg[:, i].max() > hi + 1e-6:
            print(f"WARNING J{i + 1} out of range {lo}..{hi}: {deg[:, i].min():.1f} .. {deg[:, i].max():.1f}")
    tcp = np.array([tcp_T(lay, q, prg["tool"])[:3, 3] for q in frames])
    print(f"TCP z range {tcp[:, 2].min():.0f} .. {tcp[:, 2].max():.0f} mm, max reach "
          f"{np.hypot(tcp[:, 0], tcp[:, 1]).max():.0f} mm")
    if a.csv:
        os.makedirs(os.path.dirname(a.csv), exist_ok=True)
        with open(a.csv, "w", encoding="utf-8") as fh:
            fh.write("t_s," + ",".join(f"J{i + 1}_deg" for i in range(7)) + ",tcp_x,tcp_y,tcp_z\n")
            for i, (q, p) in enumerate(zip(deg, tcp)):
                fh.write(f"{i / prg['fps']:.4f}," + ",".join(f"{v:.3f}" for v in q) + "," +
                         ",".join(f"{v:.2f}" for v in p) + "\n")
        print("trajectory ->", a.csv)
    bl = None
    if a.check or a.html:
        bl = bodies(lay, prg["tool"])
    if a.check:
        bad = check_frames(lay, frames, bl, a.check, prg["tool"])
        if bad:
            for b in bad[:30]:
                print("CONTACT frame", b[0], ":", b[1], "x", b[2], f"{b[3]:.0f} mm3" if b[3] else "")
        print(f"contact check every {a.check} frame(s):", "OK" if not bad else f"{len(bad)} problem(s)")
    if a.sw:
        write_sw(a.sw, lay, frames, a.sw_step, a.asm)
    if a.html:
        meshes, ntri = [], 0
        for nm, g, c, s in bl:
            P, I = mesh(s)
            ntri += len(I)
            meshes.append({"name": nm, "group": g, "color": c, "pos": b64(P), "idx": b64(I)})
        print(f"meshes: {len(meshes)} bodies, {ntri} triangles")
        scene = {"name": prg["name"], "fps": prg["fps"], "tool": prg["tool"],
                 "axes": [{"name": x["name"], "joint": x["joint"], "p": x["p"].tolist(), "w": x["w"].tolist()}
                          for x in lay["axes"]],
                 "flange": {"p": lay["flange"]["p"].tolist(), "w": lay["flange"]["w"].tolist()},
                 "limits": LIMITS, "events": prg["events"],
                 "tcp0": np.round(tcp_T(lay, np.zeros(len(lay["axes"])), prg["tool"]), 4).tolist(), "frames": np.round(deg, 3).tolist(), "labels": labels,
                 "meshes": meshes, "statics": statics_data(lay, prg["tool"])}
        write_html(a.html, scene)


if __name__ == "__main__":
    main()
