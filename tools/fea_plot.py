#!/usr/bin/env python3
"""Stress plots of the CalculiX pre-check (tools/fea_ccx.py) + ParaView files.

    python tools/fea_plot.py LINK-3 C [--fea fea/RTC-7] [--deform 0]
    python tools/fea_plot.py all            # every link, every case

Reads ccx/<model>.inp (tet10 mesh) and ccx/<model>.frd (nodal stresses and displacements of every step):
  * ccx/plots/<model>_<case>.png - von Mises on the surface, the whole part and a close-up round the maximum,
    the allowable stress of the case marked on the colour bar (PyVista / VTK, off screen);
  * ccx/vtu/<model>.vtu - mesh + Seqv_<case> [MPa], U_<case> [mm] for every case: open in ParaView (or any VTK
    viewer) to look at the stress distribution yourself (Warp By Vector with U_<case> - the deformed shape).
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fea_ccx as fc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_inp(path):
    nodes, elems, mode = {}, [], None
    for line in open(path):
        if line.startswith("*"):
            u = line.upper()
            mode = "N" if u.startswith("*NODE") and "PRINT" not in u and "FILE" not in u else \
                   "E" if u.startswith("*ELEMENT") else None
            continue
        if mode == "N":
            p = line.split(",")
            nodes[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]))
        elif mode == "E":
            elems.append([int(v) for v in line.split(",")[1:11]])
    return nodes, np.array(elems)


def grid(model, fea):
    """pyvista UnstructuredGrid of the tet10 mesh with the results of every case."""
    import pyvista as pv
    d = os.path.join(fea, "ccx")
    nodes, E = read_inp(os.path.join(d, model["id"] + ".inp"))
    used = np.unique(E)
    pos = {n: i for i, n in enumerate(used)}
    pts = np.array([nodes[n] for n in used])
    conn = np.vectorize(pos.get)(E)                  # CalculiX C3D10 order = VTK quadratic tetra order
    cells = np.hstack([np.full((len(conn), 1), 10), conn]).ravel()
    g = pv.UnstructuredGrid(cells, np.full(len(conn), pv.CellType.QUADRATIC_TETRA, np.uint8), pts)
    steps = fc.read_frd(os.path.join(d, model["id"] + ".frd"))
    for cs, (S, U) in zip(model["cases"], steps):
        g.point_data[f"Seqv_{cs['name']}"] = np.array([fc.mises(S[n]) if n in S else 0.0 for n in used])
        g.point_data[f"U_{cs['name']}"] = np.array([U.get(n, np.zeros(3)) for n in used])
    return g


def render(mesh, name, clim, cmap, edges, p0, size, view=(1, -1.4, 0.8)):
    """one off-screen VTK view -> RGB array (no text: VTK's font has no Cyrillic, labels come from matplotlib)"""
    import pyvista as pv
    pl = pv.Plotter(off_screen=True, window_size=size)
    pl.set_background("#ffffff")
    pl.add_mesh(mesh, scalars=name, cmap=cmap, clim=clim, show_edges=edges, edge_color="#9aa1a8", line_width=0.3,
                show_scalar_bar=False, ambient=0.55, diffuse=0.55, specular=0.0)
    pl.add_points(np.array([p0]), color="#1f5fa6", point_size=18, render_points_as_spheres=True)
    pl.view_vector(view, viewup=(0, 0, 1))
    pl.reset_camera()
    pl.camera.zoom(1.15)
    img = pl.screenshot(return_img=True)
    pl.close()
    return img


def plot(model, cs, g, cfg, out, deform):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import cm, colors
    name = cs["name"]
    key = f"Seqv_{name}"
    s = g.point_data[key]
    surf = g.extract_surface(nonlinear_subdivision=1)
    if deform:
        surf = surf.warp_by_vector(f"U_{name}", factor=deform)
    allow = cs["sigma_allow_MPa"]
    vmax = float(max(s.max(), allow * 1.05))
    i = int(np.argmax(s))
    p0 = g.points[i]
    cmap = "YlOrRd"
    z = 70.0
    close = surf.clip_box([p0[0] - z, p0[0] + z, p0[1] - z, p0[1] + z, p0[2] - z, p0[2] + z], invert=False)
    im1 = render(surf, key, (0, vmax), cmap, False, p0, (900, 1000))
    c = np.array(close.center)
    v = p0 - c
    v = v / np.linalg.norm(v) if np.linalg.norm(v) > 1e-6 else np.array([1, -1.4, -0.8])
    im2 = render(close, key, (0, vmax), cmap, True, p0, (1000, 1000), view=tuple(v + np.array([0.3, -0.4, 0.0])))
    umax = float(np.linalg.norm(g.point_data[f"U_{name}"], axis=1).max())
    fig = plt.figure(figsize=(15, 8))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.9, 1.0, 0.045], wspace=0.04, left=0.01, right=0.89, top=0.86, bottom=0.04)
    for k, (im, title) in enumerate(((im1, "вся деталь"),
                                     (im2, f"около максимума (куб ±{z:.0f} мм, видна сетка): {s.max():.0f} МПа в точке "
                                           f"({p0[0]:.0f}; {p0[1]:.0f}; {p0[2]:.0f}) мм"))):
        ax = fig.add_subplot(gs[0, k])
        ax.imshow(im)
        ax.set_axis_off()
        ax.set_title(title, fontsize=10, color="#1b2026")
    cax = fig.add_subplot(gs[0, 2])
    cb = fig.colorbar(cm.ScalarMappable(norm=colors.Normalize(0, vmax), cmap=cmap), cax=cax)
    cb.set_label("σэкв (Мизес), МПа")
    cax.axhline(allow, color="#1b2026", lw=2)
    cax.text(1.25, allow, f"допускаемое {allow:.0f}", transform=cax.get_yaxis_transform(), va="center", fontsize=9)
    sy = cfg["material"]["Sy_MPa"]
    if sy < vmax and abs(sy - allow) > 1:
        cax.axhline(sy, color="#1b2026", lw=1, ls="--")
        cax.text(1.25, sy, f"σ0,2 {sy:.0f}", transform=cax.get_yaxis_transform(), va="center", fontsize=9)
    fig.suptitle(f"{model['id']}, случай {name} — {cs['title']}\nσэкв max {s.max():.0f} МПа (синяя точка), допускаемое "
                 f"{allow:.0f} МПа (σ0,2 {sy:.0f} / запас {cs['sf_required']:g}); перемещение max {umax:.2f} мм"
                 + (f"; деформация ×{deform:g}" if deform else "") + ". CalculiX, предварительно.",
                 x=0.01, ha="left", fontsize=11.5, color="#1b2026")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{model['id']}_{name}.png")
    fig.savefig(path, dpi=110, facecolor="white")
    plt.close(fig)
    print("->", path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("case", nargs="?")
    ap.add_argument("--fea", default=os.path.join(ROOT, "fea", "RTC-7"))
    ap.add_argument("--deform", type=float, default=0.0, help="displacement scale (0 = undeformed)")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(a.fea, "rtc7_fea.json"), encoding="utf-8"))
    out = os.path.join(a.fea, "ccx", "plots")
    vdir = os.path.join(a.fea, "ccx", "vtu")
    os.makedirs(vdir, exist_ok=True)
    for m in cfg["models"]:
        if a.model != "all" and m["id"] != a.model:
            continue
        g = grid(m, a.fea)
        import vtk
        w = vtk.vtkXMLUnstructuredGridWriter()          # binary, zlib-compressed
        w.SetFileName(os.path.join(vdir, m["id"] + ".vtu"))
        w.SetInputData(g)
        w.SetCompressorTypeToZLib()
        w.SetDataModeToAppended()
        w.Write()
        for cs in m["cases"]:
            if a.case and cs["name"] != a.case:
                continue
            plot(m, cs, g, cfg, out, a.deform)


if __name__ == "__main__":
    main()
