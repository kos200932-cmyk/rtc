#!/usr/bin/env python3
"""Preview and check a BuildFromSpec description without SolidWorks.

    python tools/spec_preview.py components/DMRD/KB45/DMRD-KB45.txt [--png out.png]

Draws the half-section (X - axis, Y - radius) of every PART with its holes and PORT planes,
and checks what the macro cannot check before building:
  * profile closed, radii >= 0;
  * parts do not overlap each other (touching is fine - shafts sit in the housing bore);
  * every hole / thread starts on material and its wall stays inside the material
    over its depth (no break-out through an outer or inner diameter);
  * ports lie on a face of their part.
Exit code 1 if there are errors.
"""
import argparse
import math
import re
import sys

TAP = {"M1.6": 1.25, "M2": 1.6, "M2.5": 2.05, "M3": 2.5, "M4": 3.3, "M5": 4.2, "M6": 5,
       "M8": 6.8, "M10": 8.5, "M12": 10.2, "M14": 12, "M16": 14, "M20": 17.5}


def num(s):
    return float(s.replace(",", "."))


def parse(path):
    parts, cur, asm, data = [], None, None, {}
    with open(path, encoding="utf-8-sig") as f:
        for raw in f:
            s = re.split(r"[#;]", raw, maxsplit=1)[0].split()
            if not s:
                continue
            kw = s[0].upper()
            if kw == "ASSEMBLY":
                asm = s[1]
            elif kw == "DATA":
                data.update(kv.split("=", 1) for kv in s[1:] if "=" in kv)
            elif kw == "PART":
                cur = {"name": s[1], "pts": [], "holes": [], "ports": [], "motion": "fixed", "mass": None,
                       "cuts": []}
                parts.append(cur)
            elif kw == "END":
                cur = None
            elif cur is None:
                continue
            elif kw == "P":
                cur["pts"].append((num(s[1]), num(s[2])))
            elif kw == "MASS":
                cur["mass"] = num(s[1])
            elif kw == "MOTION":
                cur["motion"] = s[1].lower()
            elif kw in ("HOLES", "THREAD"):
                x, d_, n, pcd = num(s[1]), int(num(s[2])), int(num(s[3])), num(s[4])
                if kw == "HOLES":
                    dia, depth, label = num(s[5]), num(s[6]), f"{n}-D{s[5]}"
                else:
                    dia, depth, label = TAP[s[5].upper()], num(s[6]), f"{n}-{s[5]}"
                    nominal = num(s[5][1:])
                    depth = num(s[8]) if len(s) > 8 else depth + 0.5 * nominal
                cur["holes"].append({"x": x, "dir": -1 if d_ < 0 else 1, "n": n, "pcd": pcd,
                                     "d": dia, "depth": depth, "ang": num(s[7]), "label": label})
            elif kw == "FLATS":
                x0, x1 = num(s[1]), num(s[2])
                cur["cuts"].append({"kind": "flats", "x0": min(x0, x1), "x1": max(x0, x1), "across": num(s[3]),
                                    "n": int(num(s[4])) if len(s) > 4 else 4,
                                    "ang": num(s[5]) if len(s) > 5 else 0.0})
            elif kw == "KEYWAY":
                x, d_, L = num(s[1]), num(s[2]), num(s[3])
                x1 = x + (L if d_ >= 0 else -L)
                cur["cuts"].append({"kind": "keyway", "x0": min(x, x1), "x1": max(x, x1), "width": num(s[4]),
                                    "bottom": num(s[5]), "ang": num(s[6])})
            elif kw == "PORT":
                cur["ports"].append({"name": s[1], "x": num(s[2]), "dir": num(s[3]),
                                     "info": " ".join(s[4:])})
    parts_data = data
    return asm, parts, parts_data


def volume(p):
    """Volume of the revolved profile minus the holes (hole length taken inside the part), m^3."""
    pts, a, cy = p["pts"], 0.0, 0.0
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
        c = x1 * y2 - x2 * y1
        a += c
        cy += (y1 + y2) * c
    a /= 2
    cy /= 6 * a
    v = 2 * math.pi * abs(a) * cy
    xs = [x for x, _ in pts]
    for h in p["holes"]:
        if h["depth"] <= 0:
            L = max(xs) - min(xs)
        else:
            x0, x1 = sorted((h["x"], h["x"] + h["dir"] * h["depth"]))
            L = max(0.0, min(x1, max(xs)) - max(x0, min(xs)))
        v -= h["n"] * math.pi * h["d"] ** 2 / 4 * L
    return v * 1e-9


def inside(poly, x, y):
    """Point strictly inside or on the boundary of a polygon (even-odd rule + edge test)."""
    n, c = len(poly), False
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        # on edge
        if min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9:
            if abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) < 1e-9:
                return True
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xi:
                c = not c
    return c


def strictly_inside(poly, x, y, eps=1e-6):
    return all(inside(poly, x + dx, y + dy) for dx in (-eps, eps) for dy in (-eps, eps))


def check(parts):
    errs, notes = [], []
    for p in parts:
        if len(p["pts"]) < 3:
            errs.append(f"{p['name']}: profile has < 3 points")
        if any(y < 0 for _, y in p["pts"]):
            errs.append(f"{p['name']}: negative radius")
    # overlap between parts: sample a grid, a point strictly inside two parts = overlap
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            a, b = parts[i]["pts"], parts[j]["pts"]
            xs = [x for x, _ in a + b]
            ys = [y for _, y in a + b]
            hit = None
            x = min(xs)
            while x <= max(xs) and not hit:
                y = min(ys)
                while y <= max(ys):
                    if strictly_inside(a, x, y, 0.05) and strictly_inside(b, x, y, 0.05):
                        hit = (x, y)
                        break
                    y += 0.25
                x += 0.25
            if hit:
                errs.append(f"{parts[i]['name']} and {parts[j]['name']} overlap near x={hit[0]:.2f}, r={hit[1]:.2f}")
    # holes
    for p in parts:
        poly = p["pts"]
        xs = [x for x, _ in poly]
        for h in p["holes"]:
            r = h["pcd"] / 2
            if h["depth"] <= 0:  # through: both directions, all of the part
                x0, x1 = min(xs), max(xs)
            else:
                x0, x1 = sorted((h["x"], h["x"] + h["dir"] * h["depth"]))
            # material along the hole axis
            steps = max(2, int((x1 - x0) / 0.25))
            on_mat = [strictly_inside(poly, x0 + (x1 - x0) * k / steps, r, 0.01) for k in range(steps + 1)]
            if not any(on_mat):
                errs.append(f"{p['name']}: {h['label']} at x={h['x']} r={r} cuts no material")
                continue
            # wall break-out: at every x where the hole axis is in material, both hole edges must be too
            bad = [x0 + (x1 - x0) * k / steps for k in range(steps + 1) if on_mat[k] and not (
                inside(poly, x0 + (x1 - x0) * k / steps, r - h["d"] / 2) and
                inside(poly, x0 + (x1 - x0) * k / steps, r + h["d"] / 2))]
            if bad:
                errs.append(f"{p['name']}: {h['label']} on D{h['pcd']} breaks through a wall at x={bad[0]:.2f}")
            # holes that pass through a FLATS zone must stay inside the polygon
            for c in p["cuts"]:
                if c["kind"] != "flats" or x1 <= c["x0"] or x0 >= c["x1"]:
                    continue
                lo, hi = max(x0, c["x0"]), min(x1, c["x1"])
                if not any(strictly_inside(poly, lo + (hi - lo) * k / 20, r, 0.01) for k in range(21)):
                    continue        # the hole passes this zone in the air
                half = c["across"] / 2
                for k in range(h["n"]):
                    a = math.radians(h["ang"] + k * 360 / h["n"])
                    hy, hz = r * math.sin(a), r * math.cos(a)
                    for j in range(c["n"]):
                        b = math.radians(c["ang"] + j * 360 / c["n"])
                        if hy * math.sin(b) + hz * math.cos(b) + h["d"] / 2 > half + 1e-9:
                            errs.append(f"{p['name']}: {h['label']} hole at {math.degrees(a):.1f} deg "
                                        f"breaks through a flat (across {c['across']:g})")
                            break
            # neighbours on the same circle
            pitch = 2 * r * math.sin(math.pi / h["n"]) if h["n"] > 1 else 1e9
            if pitch < h["d"] + 1:
                errs.append(f"{p['name']}: {h['label']} holes too close (pitch {pitch:.2f})")
        for po in p["ports"]:
            on_face = any(abs(x - po["x"]) < 1e-6 for x in xs)
            if not on_face:
                notes.append(f"{p['name']}: PORT {po['name']} at x={po['x']} is not on a face of the profile")
    return errs, notes


def draw(asm, parts, png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    colors = ["#9db4c0", "#e0a458", "#7fb069", "#c97b84", "#8e7dbe"]
    fig, ax = plt.subplots(figsize=(11, 7))
    xmax = max(x for p in parts for x, _ in p["pts"])
    for i, p in enumerate(parts):
        c = colors[i % len(colors)]
        for sgn in (1, -1):
            ax.add_patch(Polygon([(x, sgn * y) for x, y in p["pts"]], closed=True, fc=c, ec="k",
                                 lw=0.8, alpha=0.85, label=f"{p['name']} ({p['motion']})" if sgn > 0 else None))
        for h in p["holes"]:
            r = h["pcd"] / 2
            if h["depth"] <= 0:
                x0, x1 = min(x for x, _ in p["pts"]), max(x for x, _ in p["pts"])
            else:
                x0, x1 = sorted((h["x"], h["x"] + h["dir"] * h["depth"]))
            for sgn in (1, -1):
                ax.add_patch(Rectangle((x0, sgn * r - h["d"] / 2), x1 - x0, h["d"], fc="white",
                                       ec="crimson", lw=0.6, hatch="////" if "M" in h["label"] else None))
            ax.annotate(f"{h['label']} D{h['pcd']:g}", (x1 if h["dir"] > 0 else x0, r),
                        fontsize=7, color="crimson", xytext=(3, 2), textcoords="offset points")
        for c in p["cuts"]:
            if c["kind"] == "flats":
                ax.plot([c["x0"], c["x1"]], [c["across"] / 2] * 2, color="purple", ls="--", lw=1)
                ax.plot([c["x0"], c["x1"]], [-c["across"] / 2] * 2, color="purple", ls="--", lw=1)
                ax.text(c["x0"], c["across"] / 2 + 1, f"flats {c['across']:g}", fontsize=7, color="purple")
            else:
                ax.add_patch(Rectangle((c["x0"], 0), c["x1"] - c["x0"], c["bottom"], fc="none",
                                       ec="purple", lw=0.8, ls="--"))
                ax.text(c["x1"], c["bottom"], f" key {c['width']:g}", fontsize=7, color="purple")
        for po in p["ports"]:
            ax.axvline(po["x"], color="navy", lw=0.8, ls="--")
            fit = re.search(r"fit=(\S+)", po["info"])
            ax.text(po["x"], -max(y for _, y in p["pts"]) - 4, f"PORT_{po['name']}\n{fit.group(1) if fit else ''}",
                    fontsize=8, color="navy", ha="center", va="top")
    ax.axhline(0, color="k", lw=0.6, ls="-.")
    ax.set_aspect("equal")
    ax.autoscale_view()
    xmin = min(x for p in parts for x, _ in p["pts"])
    ax.set_xlim(min(-8, xmin - 8), xmax + 18)
    ax.set_xlabel("X, mm (axis)")
    ax.set_ylabel("radius, mm")
    ax.set_title(f"{asm or ''} - section through the axis (holes drawn at their PCD)")
    ax.legend(loc="upper left", fontsize=8, bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(png, dpi=130)


def draw_ends(asm, parts, png):
    """Views of both ends: from -X (input, left end) and from +X (output, right end).
    Holes are shown on the end they are drilled from (through holes on both)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle

    fig, axs = plt.subplots(1, 2, figsize=(14, 7.2))
    colors = ["#5b7c99", "#c9822b", "#4f8a3a", "#a14d5a", "#6b5ca5"]
    for side, ax in zip((-1, 1), axs):
        # screen x: from -X (side -1) the +Z axis points right, from +X it points left
        sx = 1 if side < 0 else -1
        for i, p in enumerate(parts):
            col = colors[i % len(colors)]
            for r in sorted({y for _, y in p["pts"] if y > 0}):
                ax.add_patch(Circle((0, 0), r, fill=False, ec=col, lw=0.6, alpha=0.6))
            for c in p["cuts"]:
                if c["kind"] == "flats":
                    rv = c["across"] / 2 / math.cos(math.pi / c["n"])
                    vs = []
                    for k in range(c["n"]):
                        a = math.radians(c["ang"] + 180 / c["n"] + k * 360 / c["n"])
                        vs.append((sx * rv * math.cos(a), rv * math.sin(a)))
                    ax.add_patch(Polygon(vs, closed=True, fill=False, ec="purple", lw=1.2))
                elif side < 0:
                    a = math.radians(c["ang"])
                    u, w = c["bottom"], c["width"] / 2
                    pts = [(0, -w), (u, -w), (u, w), (0, w)]
                    ax.add_patch(Polygon([(sx * (uu * math.cos(a) - vv * math.sin(a)), uu * math.sin(a) + vv * math.cos(a))
                                          for uu, vv in pts], closed=True, fill=False, ec="purple", lw=1.2))
            for h in p["holes"]:
                faces = (-1, 1) if h["depth"] <= 0 else ((-1,) if h["dir"] > 0 else (1,))
                if side not in faces:
                    continue
                r = h["pcd"] / 2
                for k in range(h["n"]):
                    a = math.radians(h["ang"] + k * 360 / h["n"])
                    cx, cy = sx * r * math.cos(a), r * math.sin(a)
                    ax.add_patch(Circle((cx, cy), h["d"] / 2, fill=False, ec="crimson", lw=1))
                a = math.radians(h["ang"])
                ax.annotate(f"{h['label']} D{h['pcd']:g}", (sx * r * math.cos(a), r * math.sin(a)),
                            fontsize=7, color="crimson", xytext=(4, 4), textcoords="offset points")
        R = max(y for p in parts for _, y in p["pts"]) * 1.08
        ax.axhline(0, color="k", lw=0.4, ls="-.")
        ax.axvline(0, color="k", lw=0.4, ls="-.")
        ax.set_xlim(-R, R)
        ax.set_ylim(-R, R)
        ax.set_aspect("equal")
        ax.set_title("from -X: input (left) end, +Z right" if side < 0 else "from +X: output (right) end, +Z left",
                     fontsize=10)
    fig.suptitle(f"{asm or ''} - end views (angle 0 = +Z, 90 = +Y up)")
    fig.tight_layout()
    fig.savefig(png, dpi=120)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--png")
    ap.add_argument("--ends", help="PNG with both end views")
    a = ap.parse_args()
    asm, parts, data = parse(a.spec)
    errs, notes = check(parts)
    masses = [p["mass"] for p in parts if p["mass"]]
    for p in parts:
        if p["mass"]:
            v = volume(p)
            print(f"mass: {p['name']}: {p['mass']:g} kg, model volume {v * 1e6:.1f} cm3 "
                  f"-> density {p['mass'] / v:.0f} kg/m3")
    if masses and "mass" in data:
        try:
            total = float(data["mass"].replace(",", "."))
            if abs(sum(masses) - total) > 1e-6:
                errs.append(f"sum of part MASS {sum(masses):g} kg != DATA mass {total:g} kg")
        except ValueError:
            pass
    for e in errs:
        print("ERROR:", e)
    for n in notes:
        print("note: ", n)
    if not errs:
        print(f"OK: {len(parts)} parts, {sum(len(p['holes']) for p in parts)} hole groups, "
              f"{sum(len(p['ports']) for p in parts)} ports")
    if a.png:
        draw(asm, parts, a.png)
    if a.ends:
        draw_ends(asm, parts, a.ends)
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
