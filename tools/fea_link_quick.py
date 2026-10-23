#!/usr/bin/env python3
"""Quick stiffness / stress check of one link with CalculiX: fixed on the previous joint's output face, loads through a
rigid body on the next joint's seat.

    python tools/fea_link_quick.py links-v2/LINK-2/LINK-2.txt --out fea/link2 --h 5 \
        --fixed "x0:-0.5..0.5,rx:0,0,137,0..93" --load "z:364.5..365.5,rz:135,0,0,88..107.5" --center 135,0,365 \
        --case "Mx 1000 N*m:0,0,0,1e6,0,0" --case ...

Selectors: "x0:a..b" - node coordinate x in [a, b]; "rx:y0,z0,?,r0..r1" - distance from the axis along X through
(y0, z0) in [r0, r1]; "rz:x0,y0,?,r0..r1" - same for an axis along Z. Several selectors in one string (comma-joined
groups separated by ';') are ANDed inside a group, groups are ORed. Case: name:Fx,Fy,Fz,Mx,My,Mz (N, N*mm).
Out: rotation and displacement of the load centre, max von Mises (whole part / away from the boundary sets).
"""
import argparse
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fea_ccx as fc  # noqa: E402
import link_build as lb  # noqa: E402


def sel(X, spec):
    out = np.zeros(len(X), bool)
    for grp in spec.split(";"):
        m = np.ones(len(X), bool)
        for item in grp.split("|"):
            k, v = item.split(":", 1)
            if k in ("x0", "y0", "z0"):
                a, b = map(float, v.split(".."))
                c = X[:, "xyz".index(k[0])]
                m &= (c >= a) & (c <= b)
            elif k in ("rx", "ry", "rz"):
                p, rr = v.rsplit(",", 1)
                p = [float(t) for t in p.split(",")]
                r0, r1 = map(float, rr.split(".."))
                ax = "xyz".index(k[1])
                o = [i for i in range(3) if i != ax]
                d = np.hypot(X[:, o[0]] - p[0], X[:, o[1]] - p[1])
                m &= (d >= r0) & (d <= r1)
        out |= m
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--h", type=float, default=5.0)
    ap.add_argument("--fixed", required=True)
    ap.add_argument("--load", required=True)
    ap.add_argument("--center", required=True)
    ap.add_argument("--case", action="append", required=True)
    ap.add_argument("--E", type=float, default=71000.0)
    ap.add_argument("--name", default="link")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    step = os.path.join(a.out, a.name + ".step")
    if a.spec.lower().endswith((".step", ".stp")):          # a ready solid (e.g. a part of the user's assembly)
        import shutil
        shutil.copyfile(a.spec, step)
    else:
        shape = lb.build_part(lb.parse(a.spec)[0][0])
        lb.write_step(shape, step)
    tags, X, E, surf, nid = fc.mesh(step, a.h)
    fixed = [int(t) for t in tags[sel(X, a.fixed)]]
    load = [int(t) for t in tags[sel(X, a.load)]]
    if not fixed or not load:
        raise SystemExit(f"empty node set: fixed {len(fixed)} load {len(load)}")
    c = [float(v) for v in a.center.split(",")]
    rp, rot = int(tags.max()) + 1, int(tags.max()) + 2
    L = ["*HEADING", "quick link check - tools/fea_link_quick.py", "*NODE"]
    L += [f"{int(t)},{x:.6f},{y:.6f},{z:.6f}" for t, (x, y, z) in zip(tags, X)]
    L += [f"{rp},{c[0]},{c[1]},{c[2]}", f"{rot},{c[0]},{c[1]},{c[2]}", "*ELEMENT,TYPE=C3D10,ELSET=EALL"]
    for i, e in enumerate(E):
        e = e[[0, 1, 2, 3, 4, 5, 6, 7, 9, 8]]
        L.append(f"{i + 1}," + ",".join(str(int(n)) for n in e))
    for nm, ids in (("NFIXED", fixed), ("NLOAD", load)):
        L.append(f"*NSET,NSET={nm}")
        L += [",".join(str(n) for n in ids[j:j + 12]) for j in range(0, len(ids), 12)]
    L += ["*NSET,NSET=NREF", f"{rp},{rot}",
          "*MATERIAL,NAME=AL", "*ELASTIC", f"{a.E},0.33", "*SOLID SECTION,ELSET=EALL,MATERIAL=AL",
          f"*RIGID BODY,NSET=NLOAD,REF NODE={rp},ROT NODE={rot}", "*BOUNDARY", "NFIXED,1,3,0.0"]
    names = []
    for cs in a.case:
        nm, v = cs.rsplit(":", 1)
        v = [float(t) for t in v.split(",")]
        names.append(nm)
        L += ["*STEP", "*STATIC", "*CLOAD,OP=NEW"]
        for k in range(3):
            L += [f"{rp},{k + 1},{v[k]}", f"{rot},{k + 1},{v[3 + k]}"]
        L += ["*NODE FILE", "U", "*EL FILE", "S", "*NODE PRINT,NSET=NREF", "U", "*END STEP"]
    job = os.path.join(a.out, a.name)
    open(job + ".inp", "w").write("\n".join(L) + "\n")
    r = subprocess.run(["ccx", "-i", a.name], cwd=a.out, capture_output=True, text=True, env=dict(os.environ, OMP_NUM_THREADS="4"))
    if not os.path.isfile(job + ".frd"):
        raise SystemExit(r.stdout[-2000:] + r.stderr[-2000:])
    steps = fc.read_frd(job + ".frd")
    from scipy.spatial import cKDTree
    Xn = {int(t): X[i] for i, t in enumerate(tags)}
    tree = cKDTree(np.array([Xn[n] for n in fixed + load]))
    far = set(int(t) for t in tags if tree.query(Xn[int(t)])[0] > 2.5 * a.h)
    print(f"nodes {len(tags)}, tets {len(E)}, h {a.h} mm, fixed {len(fixed)}, load {len(load)} nodes")
    print(f"{'case':<26}{'u_ref, mm (x y z)':>30}{'rot, mrad (x y z)':>30}{'vM max':>9}{'vM far':>9}")
    ref = []                                   # NODE PRINT of NREF per step (.dat)
    cur = None
    for line in open(job + ".dat", errors="replace"):
        if "displacements" in line and "NREF" in line.upper():
            cur = {}
            ref.append(cur)
            continue
        t = line.split()
        if cur is not None and len(t) == 4:
            try:
                cur[int(t[0])] = np.array([float(v) for v in t[1:]])
            except ValueError:
                cur = None
        elif cur is not None and t:
            cur = None
    res = []
    for i, (nm, (S, U)) in enumerate(zip(names, steps)):
        u, th = ref[i][rp], ref[i][rot] * 1e3
        vm = {n: fc.mises(s) for n, s in S.items()}
        vmax, vfar = max(vm.values()), max(vm[n] for n in far if n in vm)
        nf = max((n for n in far if n in vm), key=lambda n: vm[n])
        res.append((nm, u, th, vmax, vfar))
        print(f"{nm:<26}{' '.join(f'{x:8.3f}' for x in u):>30}{' '.join(f'{x:8.3f}' for x in th):>30}{vmax:9.1f}{vfar:9.1f}"
              f"   far max at {' '.join(f'{v:.0f}' for v in Xn[nf])}")
    return res


if __name__ == "__main__":
    main()
