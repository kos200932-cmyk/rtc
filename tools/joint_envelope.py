#!/usr/bin/env python3
"""Envelope of a joint (reducer + motor + designed parts) along its own axis, in the joint frame.

    python tools/joint_envelope.py [joints/SHM-500/SHM-500.txt ...]     (no argument - all joints)

The joint frame is the reducer frame (X = axis, reducer at x > 0, motor at x < 0, output face at
the largest x). Sources: the reducer spec (revolved profiles), the PARTS file of the joint and the
motor card (stator envelope_od / envelope_x, or the actuator body for AK80-9), placed by PLACE.
Returns per joint: central bore D (smallest inner diameter of all parts - the cable passage), fixed profile (x0, x1, r) segments, the rotating output shaft, the output face x,
the base (mounting) face x, the rear end x, max radius of the fixed part and of the output flange.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_preview as sp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _kv(tokens):
    return dict(t.split("=", 1) for t in tokens if "=" in t)


def read_joint(path):
    j = {"use": {}, "parts": None, "place": {}, "out": {}, "dir": os.path.dirname(path)}
    for raw in open(path, encoding="utf-8"):
        t = re.split(r"#", raw, maxsplit=1)[0].split()
        if not t:
            continue
        k = t[0].upper()
        if k == "JOINT":
            j["name"] = t[1]
        elif k == "USE":
            j["use"][t[1]] = t[3]
        elif k == "PARTS":
            j["parts"] = t[1]
        elif k == "PLACE":
            j["place"][t[1]] = (float(t[2]), "flip" in t[3:])
        elif k == "OUT":
            j["out"][t[1]] = t[2]
    return j


def poly_segments(pts):
    """Revolved closed profile -> (x0, x1, rmax) per edge span (conservative outer radius)."""
    xs = [p[0] for p in pts]
    return (min(xs), max(xs), max(p[1] for p in pts))


def motor_envelope(card_path, x_place, flip):
    txt = open(card_path, encoding="utf-8").read()
    segs = []
    m = re.search(r"PORT\s+stator.*?envelope_od=([\d.]+)\s+envelope_x=([-\d.]+)\.\.([-\d.]+)", txt)
    if m:
        od, a, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        segs.append((a, b, od / 2))
        m2 = re.search(r"leads_x=([-\d.]+)\.\.([-\d.]+)", txt)
        if m2:   # lead wires: keep the length, inside the winding diameter
            segs.append((float(m2.group(1)), float(m2.group(2)), od / 2 - 6))
    else:        # actuator (AK80-9): DATA OD= L=, body at x -L..0
        d = _kv(re.search(r"DATA\s+(.*)", txt).group(1).split())
        segs.append((-float(d["L"]), 0.0, float(d["OD"]) / 2))
    out = []
    for a, b, r in segs:
        if flip:
            a, b = -b, -a
        out.append((x_place + a, x_place + b, r))
    return out


def envelope(joint_path, rear_allowance=25.0):   # 25 mm on the rear cover for the sensors (user, 2026-10-18)
    j = read_joint(joint_path)
    red = os.path.join(ROOT, j["use"]["reducer"])
    _, rparts, _ = sp.parse(red)
    parts = list(rparts)
    if j["parts"]:
        _, pp, _ = sp.parse(os.path.join(j["dir"], j["parts"]))
        parts += pp
    fixed, rot, out_shaft = [], [], None
    profiles = []     # exact revolved profiles (joint frame) for interference checks
    bore = min((min(y for _, y in p["pts"]) for p in parts if p["pts"]), default=0.0)
    ports = {}
    for p in parts:
        if not p["pts"]:
            continue
        s = poly_segments(p["pts"])
        (fixed if p["motion"] == "fixed" else rot).append(s + (p["name"],))
        profiles.append((p["name"], "fixed" if p["motion"] == "fixed" else "rot", list(p["pts"])))
        if p["name"].endswith("OutputShaft"):
            out_shaft = s
        for po in p["ports"]:
            ports[po["name"]] = po["x"]
    xp, flip = j["place"].get("motor", (0.0, False))
    for a, b, r in motor_envelope(os.path.join(ROOT, j["use"]["motor"]), xp, flip):
        fixed.append((a, b, r, "motor"))
        profiles.append(("motor", "motor", [(a, 0.0), (b, 0.0), (b, r), (a, r)]))
    base_ref = j["out"].get("base", "reducer.base").split(".")[1]
    x_out = out_shaft[1]
    x_rear = min(s[0] for s in fixed + rot) - rear_allowance
    r_fixed = max(s[2] for s in fixed)
    # rear cover: closes the motor housing -> its OD = the largest fixed radius within the last 10 mm of the
    # fixed parts (was 0.7 R - too big for the flange layout, where R is the link flange); never above 0.7 R
    x_fix0 = min(x for nm, kind, pts in profiles if kind == "fixed" for x, _ in pts)
    r_back = [y for nm, kind, pts in profiles if kind == "fixed" for x, y in pts if x <= x_fix0 + 10.0]
    r_cover = min(r_fixed * 0.7, max(r_back)) if r_back else r_fixed * 0.7
    return {"name": j["name"], "fixed": fixed, "rot": rot, "x_out": x_out, "x_rear": x_rear,
            "x_base": ports.get(base_ref, ports.get("base")), "R": r_fixed, "R_out": out_shaft[2],
            "L": x_out - x_rear, "rear_allowance": rear_allowance, "bore": 2 * bore,
            "profiles": profiles + [("cover", "cover", [(x_rear, 0.0), (x_rear + rear_allowance, 0.0),
                                                       (x_rear + rear_allowance, r_cover),
                                                       (x_rear, r_cover)])], "R_cover": r_cover}


def all_joints():
    jd = os.path.join(ROOT, "joints")
    res = {}
    for d in sorted(os.listdir(jd)):
        p = os.path.join(jd, d, d + ".txt")
        if os.path.isfile(p):
            e = envelope(p)
            res[e["name"]] = e
    return res


def main():
    paths = sys.argv[1:]
    envs = [envelope(p) for p in paths] if paths else list(all_joints().values())
    print("joint      rear(+allow)  base   output   length   R fixed   R output  bore D")
    for e in envs:
        print(f"{e['name']:<10} {e['x_rear']:>8.1f} {e['x_base']:>8.1f} {e['x_out']:>8.1f} {e['L']:>8.1f}"
              f" {e['R']:>8.1f} {e['R_out']:>9.1f} {e['bore']:>7.1f}")


if __name__ == "__main__":
    main()
