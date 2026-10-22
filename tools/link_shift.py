#!/usr/bin/env python3
"""Shift a prismatic link spec (links*/LINK-n) along X / Y / Z in the world frame, keeping the comments.

    python tools/link_shift.py links-v2/LINK-3/LINK-3.txt --dx 30 [--dy 0] [--dz 0] [--note "..."]

PRISM / CUT: the extrusion levels a0 a1 move with the shift along their own axis, the shape coordinates (u, v) with
the shift in the plane (X plane: u=y v=z; Y plane: u=x v=z; Z plane: u=x v=y). TAP: levels + centre. PORTP: level.
"""
import argparse
import re

UV = {"X": ("y", "z"), "Y": ("x", "z"), "Z": ("x", "y")}


def f(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--dx", type=float, default=0.0)
    ap.add_argument("--dy", type=float, default=0.0)
    ap.add_argument("--dz", type=float, default=0.0)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    d = {"x": a.dx, "y": a.dy, "z": a.dz}
    raw = open(a.spec, "rb").read().decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in raw else "\n"
    out = []
    for line in raw.split(nl):
        m = re.match(r"^(\s*)(\S.*?)(\s*[#;].*)?$", line)
        if not m or line.lstrip().startswith(("#", ";")):
            out.append(line)
            continue
        ind, body, com = m.group(1), m.group(2), m.group(3) or ""
        t = body.split()
        k = t[0].upper()
        if k in ("PRISM", "CUT", "TAP", "PORTP"):
            ax = t[1].upper() if k != "PORTP" else t[2].upper()
            da = d[ax.lower()]
            du, dv = (d[c] for c in UV[ax])
            if k == "PORTP":
                t[3] = f(float(t[3]) + da)
            else:
                t[2], t[3] = f(float(t[2]) + da), f(float(t[3]) + da)
            if k == "TAP":
                t[4], t[5] = f(float(t[4]) + du), f(float(t[5]) + dv)
            elif k in ("PRISM", "CUT"):
                sh, v = t[4].upper(), [float(x) for x in t[5:]]
                if sh == "RECT":
                    v[0] += du; v[1] += du; v[2] += dv; v[3] += dv
                elif sh in ("CIRC", "RING", "PATTERN"):
                    v[0] += du; v[1] += dv
                elif sh == "POLY":
                    for i in range(0, len(v), 2):
                        v[i] += du; v[i + 1] += dv
                elif sh == "RPOLY":
                    for i in range(0, len(v), 3):
                        v[i] += du; v[i + 1] += dv
                t = t[:5] + [f(x) for x in v]
            line = ind + " ".join(t) + com
        out.append(line)
    if a.note:
        out.insert(0, "# " + a.note)
    open(a.spec, "w", encoding="utf-8", newline="").write(nl.join(out))
    print("shifted", a.spec, d)


if __name__ == "__main__":
    main()
