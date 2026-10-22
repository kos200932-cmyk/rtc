#!/usr/bin/env python3
"""Kinematic scheme of the arm from a layout file (robot/*-layout.txt).

    python tools/robot_scheme.py robot/RTC-7-layout.txt [--png out.png] [--md out.md]
                                 [--pose 0,30,0,60,0,45,0]

The layout gives every joint axis in the zero configuration (point + direction, see AXIS)
and the tool flange (FLANGE). From that the script
  * builds the forward kinematics (product of exponentials - exact, no conventions);
  * derives the standard Denavit-Hartenberg table (Spong convention) and checks it against
    the PoE model on random poses;
  * prints the axis relations (intersect / parallel / offsets), reach;
  * draws the scheme: zero pose as on the drawing + a 3D view of a test pose.
Needs numpy, matplotlib.
"""
import argparse
import math
import re
import sys

import numpy as np

R_SYMBOL = {"SHM-60": 55, "SHM-150": 71, "SHM-500": 95, "SHM-1000": 95, "SHM-150m": 120,
            "SHM-KB25": 68, "SHM-KB25m": 120, "SHM-KB32": 86, "SHM-KB45": 110, "SHM-KB50": 126}   # ~ real envelope radius
L_SYMBOL = {"SHM-60": 85, "SHM-150": 100, "SHM-500": 140, "SHM-1000": 190, "SHM-150m": 100,
            "SHM-KB25": 129, "SHM-KB25m": 100, "SHM-KB32": 137, "SHM-KB45": 165, "SHM-KB50": 184}  # ~ real envelope length


def read_layout(path):
    lay = {"axes": [], "flange": None, "name": "?", "notes": []}
    for raw in open(path, encoding="utf-8"):
        t = re.split(r"#", raw, maxsplit=1)[0].split()
        if not t:
            continue
        if t[0] == "ROBOT":
            lay["name"] = t[1]
        elif t[0] == "AXIS":
            kv = dict(x.split("=", 1) for x in t[9:] if "=" in x)
            lay["axes"].append({"name": t[1], "joint": t[2],
                                "p": np.array([float(v) for v in t[3:6]]),
                                "w": np.array([float(v) for v in t[6:9]]),
                                "motor": kv.get("motor"), "output": kv.get("output"),
                                "at": float(kv["at"]) if "at" in kv else None,
                                "face": np.array([float(v) for v in kv["face"].split(",")]) if "face" in kv else None})
        elif t[0] == "CABLE":
            lay.setdefault("cable", []).append(("arc", *map(float, t[2:7])) if t[1] == "arc"
                                               else ("pt", float(t[2]), float(t[3])))
        elif t[0] == "FLANGE":
            lay["flange"] = {"p": np.array([float(v) for v in t[1:4]]),
                             "w": np.array([float(v) for v in t[4:7]]),
                             "assumed": "ASSUMED" in t[7:]}
    for a in lay["axes"]:
        a["w"] = a["w"] / np.linalg.norm(a["w"])
    return lay


# ---------------------------------------------------------------- PoE
def rot(w, q):
    w = np.asarray(w, float)
    k = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    return np.eye(3) + math.sin(q) * k + (1 - math.cos(q)) * k @ k


def screw_T(w, p, q):
    """Rotation by q about the line (p, w)."""
    T = np.eye(4)
    R = rot(w, q)
    T[:3, :3] = R
    T[:3, 3] = p - R @ p
    return T


def flange_M(lay):
    """Tool frame at zero: origin on the flange, z = flange axis, x = world X projected."""
    f = lay["flange"]
    z = f["w"] / np.linalg.norm(f["w"])
    x = np.array([1.0, 0, 0]) - z * z[0]
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0, 1.0, 0]) - z * z[1]
    x /= np.linalg.norm(x)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, np.cross(z, x), z, f["p"]
    return M


def fk_poe(lay, q):
    """Frames of all joints (as moved) and of the flange for joint angles q (rad)."""
    T = np.eye(4)
    pts, dirs, Ts = [], [], []
    for a, qi in zip(lay["axes"], q):
        # axis i is moved by joints 1..i-1
        pts.append((T @ np.r_[a["p"], 1])[:3])
        dirs.append(T[:3, :3] @ a["w"])
        Ts.append(T.copy())
        T = T @ screw_T(a["w"], a["p"], qi)
    lay["_Ts"] = Ts
    return pts, dirs, T @ flange_M(lay)


_ENV = None


def joint_bodies(lay):
    """Real envelopes (tools/joint_envelope.py) placed by face= of the layout, for the last fk_poe pose.
    Returns per joint a list of (centre, axis unit, radius, length, kind) or None."""
    global _ENV
    if _ENV is None:
        try:
            import joint_envelope
            _ENV = joint_envelope.all_joints()
        except Exception as ex:          # noqa: BLE001
            print("no joint envelopes:", ex)
            _ENV = {}
    out = []
    for a, T in zip(lay["axes"], lay.get("_Ts", [])):
        e = _ENV.get(a["joint"]) or _ENV.get(a["joint"].rstrip("m"))
        if e is None or a.get("face") is None:
            out.append(None)
            continue
        md = np.zeros(3)
        md["XYZ".index(a["motor"][1])] = 1 if a["motor"][0] == "+" else -1
        u = -md                                    # joint local +X (toward the output) in the world
        segs = []
        for kind, lst in (("fixed", e["fixed"]), ("rot", e["rot"])):
            for x0, x1, r, name in lst:
                k = "motor" if name == "motor" else kind
                c = a["face"] + u * ((x0 + x1) / 2 - e["x_out"])
                segs.append(((T @ np.r_[c, 1])[:3], T[:3, :3] @ u, r, x1 - x0, k))
        # rear allowance (cover) as a thin disc
        xr = e["x_rear"]
        c = a["face"] + u * (xr + e["rear_allowance"] / 2 - e["x_out"])
        segs.append(((T @ np.r_[c, 1])[:3], T[:3, :3] @ u, e["R"] * 0.7, e["rear_allowance"], "cover"))
        if a["joint"].endswith("m"):      # ШМ-150м: + ОПУ RU178G at z -28..0 (outer ring fixed, inner turns)
            segs.append((np.array([0, 0, -14.0]), np.array([0, 0, 1.0]), 120.0, 28.0, "fixed"))
            segs.append((np.array([0, 0, -14.0]), np.array([0, 0, 1.0]), 88.5, 28.0, "rot"))
        out.append(segs)
    return out


def cable_xy(lay):
    """Cable centre line (zero pose) as a polyline in the X-Z plane."""
    P = []
    for item in lay.get("cable", []):
        if item[0] == "pt":
            P.append((item[1], item[2]))
        else:
            _, cx, cz, r, a0, a1 = item
            for tt in np.linspace(math.radians(a0), math.radians(a1), 24):
                P.append((cx + r * math.cos(tt), cz + r * math.sin(tt)))
    return np.array(P)


# ---------------------------------------------------------------- DH
def line_relation(p1, w1, p2, w2, tol=1e-6):
    """Common normal of two lines: returns (kind, point on 1, point on 2)."""
    n = np.cross(w1, w2)
    d = p2 - p1
    if np.linalg.norm(n) < tol:                       # parallel
        t = d - w1 * (d @ w1)
        return ("coincident" if np.linalg.norm(t) < 1e-6 else "parallel"), p1, p1 + t
    # closest points
    A = np.array([[w1 @ w1, -w1 @ w2], [w1 @ w2, -w2 @ w2]])
    s, u = np.linalg.solve(A, [d @ w1, d @ w2])
    c1, c2 = p1 + s * w1, p2 + u * w2
    return ("intersect" if np.linalg.norm(c2 - c1) < 1e-6 else "skew"), c1, c2


def dh_from_axes(lay):
    """Standard DH (Spong): z_{i-1} = axis i. Returns base frame T0 and rows (theta0, d, a, alpha)."""
    axes = lay["axes"]
    lines = [(a["p"], a["w"]) for a in axes]
    fl = lay["flange"]
    # frame 0: origin on axis 1 at its point, z0 = axis 1, x0 = world X (or Y) projected
    z = lines[0][1]
    x = np.array([1.0, 0, 0]) - z * z[0]
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0, 1.0, 0]) - z * z[1]
    x /= np.linalg.norm(x)
    frames = [(lines[0][0].copy(), x, np.cross(z, x), z)]
    nxt = lines[1:] + [(fl["p"], fl["w"])]
    for i, (p2, w2) in enumerate(nxt):
        o1, x1, _, z1 = frames[-1]
        kind, c1, c2 = line_relation(o1, z1, p2, w2)
        if kind == "coincident":                          # same axis (flange): x of the tool frame
            o, xi = p2.copy(), flange_M(lay)[:3, 0]
        elif kind == "parallel":
            o = c2
            xi = (c2 - c1) / np.linalg.norm(c2 - c1)
        elif kind == "intersect":
            o = c2
            xi = np.cross(z1, w2)
            xi /= np.linalg.norm(xi)
            if xi @ x1 < -1e-9:                            # keep theta0 small
                xi = -xi
        else:
            o = c2
            xi = (c2 - c1) / np.linalg.norm(c2 - c1)
        frames.append((o, xi, np.cross(w2, xi), w2))
    rows = []
    for i in range(1, len(frames)):
        o0, x0, y0, z0 = frames[i - 1]
        o1, x1, y1, z1 = frames[i]
        d = (o1 - o0) @ z0
        a = (o1 - o0) @ x1
        theta = math.atan2(np.cross(x0, x1) @ z0, x0 @ x1)
        alpha = math.atan2(np.cross(z0, z1) @ x1, z0 @ z1)
        rows.append((theta, d, a, alpha))
    o, x, y, z = frames[0]
    T0 = np.eye(4)
    T0[:3, 0], T0[:3, 1], T0[:3, 2], T0[:3, 3] = x, y, z, o
    return T0, rows, frames


def dh_A(theta, d, a, alpha):
    ct, st, ca, sa = math.cos(theta), math.sin(theta), math.cos(alpha), math.sin(alpha)
    return np.array([[ct, -st * ca, st * sa, a * ct],
                     [st, ct * ca, -ct * sa, a * st],
                     [0, sa, ca, d],
                     [0, 0, 0, 1]])


def fk_dh(T0, rows, q):
    T = T0.copy()
    for i, (th, d, a, al) in enumerate(rows):
        T = T @ dh_A(th + (q[i] if i < len(q) else 0.0), d, a, al)
    return T


# ---------------------------------------------------------------- drawing
def cylinder(ax, c, w, r, L, color, alpha=0.55):
    w = w / np.linalg.norm(w)
    u = np.cross(w, [1, 0, 0] if abs(w[0]) < 0.9 else [0, 1, 0])
    u /= np.linalg.norm(u)
    v = np.cross(w, u)
    t = np.linspace(0, 2 * math.pi, 28)
    s = np.array([-L / 2, L / 2])
    T, S = np.meshgrid(t, s)
    P = (c[:, None, None] + w[:, None, None] * S + r * (u[:, None, None] * np.cos(T) + v[:, None, None] * np.sin(T)))
    ax.plot_surface(P[0], P[1], P[2], color=color, alpha=alpha, linewidth=0, shade=True)
    for sg in (-1, 1):
        ring = c[:, None] + w[:, None] * sg * L / 2 + r * (u[:, None] * np.cos(t) + v[:, None] * np.sin(t))
        ax.plot(*ring, color="k", lw=0.5)


COLORS = {"SHM-60": "#e6a23c", "SHM-150": "#67c23a", "SHM-500": "#409eff", "SHM-1000": "#f56c6c",
          "SHM-150m": "#9b59b6", "SHM-KB25": "#67c23a", "SHM-KB25m": "#9b59b6", "SHM-KB32": "#2bb3a3",
          "SHM-KB45": "#409eff", "SHM-KB50": "#3366cc"}


def body_centres(lay, pts, dirs, flange_p):
    """Where to draw each joint symbol: pitch joints between the two arm lines, roll joints on the link."""
    out = []
    n = len(pts)
    for i in range(n):
        j = lay["axes"][i]["joint"]
        if lay["axes"][i].get("at") is not None:           # body position given in the layout
            out.append(pts[i] + dirs[i] * lay["axes"][i]["at"])
            continue
        if i == 0:
            out.append(pts[0] - dirs[0] * L_SYMBOL[j] / 2)
            continue
        prev_line = pts[i - 1]
        # point of axis i closest to axis i-1 and to axis i+1
        _, _, c_prev = line_relation(pts[i - 1], dirs[i - 1], pts[i], dirs[i])
        if i + 1 < n:
            _, _, c_next = line_relation(pts[i + 1], dirs[i + 1], pts[i], dirs[i])
        else:
            c_next = flange_p
        if abs(dirs[i] @ dirs[i - 1]) < 0.5:          # pitch joint (axis across the arm)
            out.append((c_prev + c_next) / 2)
        else:                                          # roll joint: on the link, after the previous joint
            L = L_SYMBOL[j]
            seg = c_next - c_prev
            k = min(0.5, (R_SYMBOL[lay["axes"][i - 1]["joint"]] + L / 2 + 15) / max(np.linalg.norm(seg), 1))
            out.append(c_prev + seg * (k if i + 1 < n else 1) - (0 if i + 1 < n else dirs[i] * L / 2))
    return out


def draw_side(ax, lay, zoom=None, title=None):
    """Zero pose as on the user's scheme: base at the bottom, +Z up, +X to the right (view along +Y)."""
    from matplotlib.patches import Rectangle
    n = len(lay["axes"])
    pts, dirs, Tf = fk_poe(lay, np.zeros(n))
    cen = body_centres(lay, pts, dirs, Tf[:3, 3])
    uv = lambda P: (P[0], P[2])
    chain = [pts[0]]
    for i in range(n - 1):
        _, c1, c2 = line_relation(pts[i], dirs[i], pts[i + 1], dirs[i + 1])
        chain += [c1, c2]
    chain.append(Tf[:3, 3])
    U = np.array([uv(P) for P in chain])
    ax.plot(U[:, 0], U[:, 1], color="0.3", lw=2.5, zorder=1)
    bodies = joint_bodies(lay)
    for i, a in enumerate(lay["axes"]):
        j, c, w = a["joint"], cen[i], dirs[i]
        r, L = R_SYMBOL[j], L_SYMBOL[j]
        along_z = abs(w[2]) > 0.5
        if bodies[i]:
            style = {"fixed": dict(fc=COLORS[j], ec="k", alpha=0.55, lw=0.6),
                     "rot": dict(fc="0.55", ec="k", alpha=0.9, lw=0.6),
                     "motor": dict(fc="none", ec="k", hatch="////", lw=0.6),
                     "cover": dict(fc="none", ec="0.4", ls=":", lw=0.8)}
            for sc, su, sr, sl, kind in bodies[i]:
                cu_, cv_ = uv(sc)
                wu, hv = (2 * sr, sl) if abs(su[2]) > 0.5 else (sl, 2 * sr)
                ax.add_patch(Rectangle((cu_ - wu / 2, cv_ - hv / 2), wu, hv, zorder=2 + (kind != "fixed"),
                                       **style[kind]))
            c = np.mean([b[0] for b in bodies[i]], axis=0)
            cen[i] = c
            r = max(b[2] for b in bodies[i])
            L = max(np.abs((b[0] - c) @ w) + b[3] / 2 for b in bodies[i]) * 2
        else:
            cu, cv = uv(c)
            wu, hv = (2 * r, L) if along_z else (L, 2 * r)
            ax.add_patch(Rectangle((cu - wu / 2, cv - hv / 2), wu, hv, fc=COLORS[j], ec="k", alpha=0.8, zorder=2))
            sgn = 1 if a["motor"].startswith("+") else -1
            md = np.zeros(3); md["XYZ".index(a["motor"][1])] = sgn
            mu, mv = uv(c + md * (L / 2 - 12))
            bw, bh = (2 * r, 24) if along_z else (24, 2 * r)
            ax.add_patch(Rectangle((mu - bw / 2, mv - bh / 2), bw, bh, fc="none", ec="k", hatch="////", zorder=3))
        cu, cv = uv(c)
        e = w * (L / 2 + 60)
        (u0, v0), (u1, v1) = uv(c - e), uv(c + e)
        ax.plot([u0, u1], [v0, v1], color="#e67e22", ls="-.", lw=1, zorder=4)
        ax.annotate("", xy=(u1, v1), xytext=(u0 + (u1 - u0) * 0.8, v0 + (v1 - v0) * 0.8),
                    arrowprops=dict(arrowstyle="->", color="r", lw=1.3), zorder=5)
        if bodies[i]:
            ax.text(cu + (r + 15 if along_z else 0), cv + (0 if along_z else r + 15), f"{a['name']} {j}",
                    ha="left" if along_z else "center", va="center" if along_z else "bottom", fontsize=8, zorder=6)
        else:
            ax.text(cu, cv, f"{a['name']}\n{j}", ha="center", va="center", fontsize=8, zorder=6)
    C = cable_xy(lay)
    if len(C):
        ax.plot(C[:, 0], C[:, 1], color="#c0392b", lw=1.6, zorder=7, label="cable")
    fu, fv = uv(Tf[:3, 3])
    ax.plot([fu - 50, fu + 50], [fv, fv], color="k", lw=3)
    ax.text(fu, fv + 25, "flange (estimated)" if lay["flange"]["assumed"] else "flange", ha="center", fontsize=8)
    # dimensions: heights of the horizontal axes, lateral offsets of the vertical ones
    zs = [0] + [p[2] for p, w in zip(pts, dirs) if abs(w[2]) < 0.5]
    xs = sorted({round(p[0], 3) for p, w in zip(pts, dirs) if abs(w[2]) > 0.5})
    xr = max(xs) + 250
    for z0, z1 in zip(zs[:-1], zs[1:]):
        ax.annotate("", xy=(xr, z0), xytext=(xr, z1), arrowprops=dict(arrowstyle="<->", lw=0.8, color="b"))
        ax.text(xr + 15, (z0 + z1) / 2, f"{z1 - z0:.0f}", color="b", va="center", fontsize=9, rotation=90)
        ax.plot([xs[0], xr + 10], [z1, z1], color="b", lw=0.3)
    if len(xs) > 1:
        ax.annotate("", xy=(xs[0], -120), xytext=(xs[-1], -120), arrowprops=dict(arrowstyle="<->", lw=0.8, color="b"))
        ax.text((xs[0] + xs[-1]) / 2, -110, f"{xs[-1] - xs[0]:.0f}", color="b", ha="center", fontsize=9)
    ax.annotate("", xy=(150, 0), xytext=(0, 0), arrowprops=dict(arrowstyle="->", color="r", lw=1.5))
    ax.text(155, -10, "X", color="r")
    ax.annotate("", xy=(0, 150), xytext=(0, 0), arrowprops=dict(arrowstyle="->", color="b", lw=1.5))
    ax.text(-30, 155, "Z", color="b")
    ax.set_aspect("equal")
    if zoom:
        ax.set_xlim(*zoom[0]), ax.set_ylim(*zoom[1])
        for txt in ax.texts:
            txt.set_clip_on(True)
            if hasattr(txt, "set_annotation_clip"):
                txt.set_annotation_clip(True)
        ax.grid(True, lw=0.3, color="0.85")
        ax.tick_params(labelsize=7)
        for sp_ in ax.spines.values():
            sp_.set_color("0.7")
    else:
        ax.set_xlim(min(xs) - 450, xr + 120), ax.set_ylim(-250, fv + 150)
        ax.axis("off")
    ax.set_title(title or "zero pose (view along +Y): hatched = motor, grey = rotating, red = cable", fontsize=10)


def draw(lay, q_test, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(20, 15))
    gs = fig.add_gridspec(3, 3, width_ratios=[1.0, 1.1, 1.3])
    draw_side(fig.add_subplot(gs[:, 0]), lay)
    n = len(lay["axes"])
    pts0, _, Tf0 = fk_poe(lay, np.zeros(n))
    zz = [p[2] for p in pts0]
    for k, (za, zb, nm) in enumerate([(zz[1], zz[2], "shoulder J1-J3"), (zz[3], zz[4], "elbow J4-J5"),
                                      (zz[5], Tf0[2, 3], "wrist J6-J7, flange")]):
        lo = min(za, zb)
        xa = [p[0] for p in pts0]
        x0z, x1z = min(xa) - 180, max(xa) + 180
        hz = (x1z - x0z) * 0.75
        draw_side(fig.add_subplot(gs[2 - k, 1]), lay, zoom=((x0z, x1z), (lo - 0.4 * hz, lo + 0.6 * hz)), title=nm)
    fk_poe(lay, np.zeros(n))
    for k, (q, title) in enumerate([(np.zeros(len(lay["axes"])), "zero pose, 3D"),
                                    (q_test, "test pose q = " + ", ".join(f"{math.degrees(v):.0f}" for v in q_test))]):
        ax = fig.add_subplot(gs[k * 1:(k + 1) * 1 + (1 if k else 0), 2] if False else gs[(0 if k == 0 else 1):(1 if k == 0 else 3), 2], projection="3d")
        pts, dirs, Tf = fk_poe(lay, q)
        cen = body_centres(lay, pts, dirs, Tf[:3, 3])
        # links: chain of the common-normal points
        chain = [pts[0] - dirs[0] * 0]
        for i in range(len(pts) - 1):
            _, c1, c2 = line_relation(pts[i], dirs[i], pts[i + 1], dirs[i + 1])
            chain += [c1, c2]
        chain.append(Tf[:3, 3])
        C = np.array(chain)
        ax.plot(C[:, 0], C[:, 1], C[:, 2], color="0.25", lw=3, solid_capstyle="round")
        bodies = joint_bodies(lay)
        for i, a in enumerate(lay["axes"]):
            j = a["joint"]
            if bodies[i]:
                for sc, su, sr, sl, kind in bodies[i]:
                    if kind in ("fixed", "motor") and sr > 30:
                        cylinder(ax, sc, su, sr, sl, COLORS[j], alpha=0.35)
                cen[i] = np.mean([b[0] for b in bodies[i]], axis=0)
            else:
                cylinder(ax, cen[i], dirs[i], R_SYMBOL[j], L_SYMBOL[j], COLORS[j])
            e = dirs[i] * (L_SYMBOL[j] / 2 + 70)
            ax.plot(*np.c_[cen[i] - e, cen[i] + e], color="k", lw=0.8, ls="-.")
            ax.quiver(*(cen[i] + e * 0.6), *(dirs[i] * 45), color="r", lw=1.2, arrow_length_ratio=0.5)
            ax.text(*(cen[i] + dirs[i] * 0 + np.array([0, 0, 70])), a["name"], fontsize=8, ha="center")
        # base plate
        b = np.linspace(0, 2 * math.pi, 40)
        ax.plot(140 * np.cos(b), 140 * np.sin(b), np.full_like(b, -L_SYMBOL["SHM-150m"]), color="k", lw=1.5)
        # tool frame
        for col, vec in zip("rgb", Tf[:3, :3].T):
            ax.quiver(*Tf[:3, 3], *(vec * 90), color=col, lw=1.5, arrow_length_ratio=0.25)
        ax.text(*(Tf[:3, 3] + [0, 0, 60]), "flange" + (" (pos. assumed)" if lay["flange"]["assumed"] else ""),
                fontsize=8, ha="center")
        # world frame
        for col, vec, nm in zip("rgb", np.eye(3), "XYZ"):
            ax.quiver(0, 0, 0, *(vec * 150), color=col, lw=1, arrow_length_ratio=0.15)
            ax.text(*(vec * 175), nm, color=col, fontsize=9)
        lim = 0.55 * (np.linalg.norm(fk_poe(lay, np.zeros(len(q)))[2][:3, 3]) + 200)
        ax.set_xlim(-lim, lim), ax.set_ylim(-lim, lim), ax.set_zlim(-150, 2 * lim - 150)
        ax.set_box_aspect((1, 1, 1))
        ax.set_xlabel("X"), ax.set_ylabel("Y"), ax.set_zlabel("Z")
        ax.view_init(elev=22, azim=-55)
        ax.set_title(title, fontsize=10)
    fig.suptitle(f"{lay['name']}: kinematic scheme (red arrow = + direction of the axis)", fontsize=12)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.04, wspace=0.12, hspace=0.25)
    fig.savefig(path, dpi=110)


def deg(v):
    return f"{math.degrees(v):.1f}".replace("-0.0", "0.0")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("layout")
    ap.add_argument("--png")
    ap.add_argument("--md")
    ap.add_argument("--pose", default="20,35,-30,70,40,45,0", help="test pose, deg")
    a = ap.parse_args()
    lay = read_layout(a.layout)
    n = len(lay["axes"])
    T0, rows, frames = dh_from_axes(lay)

    # self-check DH == PoE
    rng = np.random.default_rng(1)
    err = 0.0
    for _ in range(200):
        q = rng.uniform(-math.pi, math.pi, n)
        err = max(err, np.abs(fk_poe(lay, q)[2] - fk_dh(T0, rows, q)).max())

    out = [f"# {lay['name']}: kinematics (`python tools/robot_scheme.py {a.layout}`)", "",
           "Zero configuration = the arm stretched as on the scheme. World frame: origin on the J1 axis at the",
           "mounting face of the slewing bearing, +Z along J1 toward the arm, +X toward the lateral offsets.", "",
           "## Joint axes (zero configuration)", "",
           "| Joint | Drive | Point on the axis, mm | Direction | Motor side | Relation to the previous axis |",
           "|---|---|---|---|---|---|"]
    for i, ax_ in enumerate(lay["axes"]):
        rel = ""
        if i:
            pr = lay["axes"][i - 1]
            kind, c1, c2 = line_relation(pr["p"], pr["w"], ax_["p"], ax_["w"])
            ang = math.degrees(math.acos(min(1, abs(pr["w"] @ ax_["w"]))))
            rel = f"{kind}, {ang:.0f} deg" + (f", distance {np.linalg.norm(c2 - c1):.0f}" if kind in ("parallel", "skew") else "")
        out.append(f"| {ax_['name']} | {ax_['joint']} | {', '.join(f'{v:g}' for v in ax_['p'])} | "
                   f"{', '.join(f'{v:g}' for v in ax_['w'])} | {ax_['motor']} | {rel} |")
    f = lay["flange"]
    out += ["", f"Flange: {', '.join(f'{v:g}' for v in f['p'])}" + ("  (ASSUMED - not dimensioned on the scheme)" if f["assumed"] else ""),
            "", "## Standard DH (Spong): A_i = Rz(theta_i) Tz(d_i) Tx(a_i) Rx(alpha_i), theta_i = q_i + offset_i", "",
            "| i | offset theta, deg | d, mm | a, mm | alpha, deg |", "|---|---|---|---|---|"]
    for i, (th, d, aa, al) in enumerate(rows):
        nm = lay["axes"][i]["name"] if i < n else "flange"
        out.append(f"| {i + 1} ({nm}) | {deg(th)} | {d:.1f} | {aa:.1f} | {deg(al)} |")
    out += ["", f"Row {n} ends in the tool frame on the flange (x = world X at zero). Base frame of the DH chain = world frame"
            + (" (identity)." if np.allclose(T0, np.eye(4)) else ":\n\n```\n" + np.array2string(T0, precision=3) + "\n```"),
            "", f"Check: DH chain vs exact axis model on 200 random poses - max difference {err:.1e} (mm / -)."]
    # geometry summary
    _, _, Tz = fk_poe(lay, np.zeros(n))
    sh = lay["axes"][1]["p"]
    wr = lay["axes"][5]["p"] if n > 5 else None
    out += ["", "## Geometry", "",
            f"- shoulder (J2 x J1) at z = {sh[2]:.0f}; flange at zero pose {', '.join(f'{v:.0f}' for v in Tz[:3, 3])}",
            f"- J2 -> J6 (shoulder -> wrist pitch) along the arm: {np.linalg.norm(wr - sh):.0f} mm" if wr is not None else "",
            f"- reach from the shoulder axis to the flange: {np.linalg.norm(Tz[:3, 3] - sh):.0f} mm (with the assumed flange)",
            "- consecutive axes all intersect: the lateral offsets lie along the pitch axes (out of the bending plane)"
            if all(line_relation(x["p"], x["w"], y["p"], y["w"])[0] == "intersect"
                   for x, y in zip(lay["axes"][:-1], lay["axes"][1:])) else "- not all consecutive axes intersect (see the table)"]
    report = "\n".join(x for x in out if x is not None) + "\n"
    print(report)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(report)
    if a.png:
        draw(lay, np.radians([float(v) for v in a.pose.split(",")]), a.png)
        print("scheme ->", a.png)
    if err > 1e-6:
        sys.exit("DH check FAILED")


if __name__ == "__main__":
    main()
