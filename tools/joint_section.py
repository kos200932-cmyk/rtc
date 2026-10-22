#!/usr/bin/env python3
"""Half section of a flange-layout joint (reducer + motor + designed parts + the link and the screws) as a picture.

    python tools/joint_section.py joints/SHM-KB45/SHM-KB45.txt [...] [--png out.png]

Reads the joint (USE reducer / motor, PARTS, PLACE), the base port of the flange housing (link bore, screw circle) and
its reducer port; draws the upper half (x - joint axis, r - radius) with the previous link on the reducer side of the
flange and both screw sets (flange -> reducer from the output side, link -> flange from the motor side).
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_envelope as je  # noqa: E402
import spec_preview as sp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK, MUTE = "#1b2026", "#5d6670"
HEAD = {"M3": (5.5, 3), "M4": (7, 4), "M5": (8.5, 5), "M6": (10, 6), "M8": (13, 8)}   # DIN912 head D, height


def kv(info):
    return dict(t.split("=", 1) for t in info.split() if "=" in t)


def draw(ax, path):
    from matplotlib.patches import Polygon, Rectangle
    j = je.read_joint(path)
    _, red, _ = sp.parse(os.path.join(ROOT, j["use"]["reducer"]))
    _, prt, _ = sp.parse(os.path.join(j["dir"], j["parts"]))
    col = {"Housing": "#b8c2cc", "InputShaft": "#e3b36e", "OutputShaft": "#8fbf7f", "RotorCup": "#d98c5f",
           "ClampFlange": "#c9a0dc", "StatorClamp": "#9aa1a8", "FlangeHousing": "#2a5d9f"}
    for p in red + prt:
        k = p["name"].split("_")[-1]
        ax.add_patch(Polygon(p["pts"], closed=True, fc=col.get(k, "#ccc"), ec="k", lw=0.7,
                             alpha=0.85 if k == "FlangeHousing" else 1, zorder=3 if k == "FlangeHousing" else 2))
    xp, flip = j["place"].get("motor", (0.0, False))
    for a, b, r in je.motor_envelope(os.path.join(ROOT, j["use"]["motor"]), xp, flip)[:1]:
        ax.add_patch(Rectangle((a, r * 0.72), b - a, r * 0.28, fc="#555b63", ec="k", lw=0.6, zorder=2))
    fh = next(p for p in prt if p["name"].endswith("FlangeHousing"))
    base = kv(next(po for po in fh["ports"] if po["name"] == "base")["info"])
    redp = kv(next(po for po in fh["ports"] if po["name"] == "reducer")["info"])
    xb = next(po for po in fh["ports"] if po["name"] == "base")["x"]
    r_link = float(base["link_bore"].rstrip("H7")) / 2
    r_fl = max(y for _, y in fh["pts"])
    x_fl0 = min(x for x, y in fh["pts"] if y == r_fl)
    ring = next(p for p in red if p["name"].endswith("Housing"))
    x_ring1 = max(x for x, y in ring["pts"] if y == max(yy for _, yy in ring["pts"]))
    # link (previous) on the reducer side of the flange, its bore on the reducer ring
    t_link = 16
    ax.add_patch(Rectangle((xb, r_link), t_link, r_fl + 14 - r_link, fc="#f2e6c9", ec="k", lw=0.8, hatch="///", zorder=1))
    # screws
    n, size = base["screws"].split("_")[0].split("x")
    hd, hk = HEAD[size]
    d = float(size[1:])
    r_s = float(base["pcd"]) / 2
    ax.add_patch(Rectangle((x_fl0, r_s - d / 2), xb - x_fl0 + 1.5 * d, d, fc="#e0a100", ec="k", lw=0.5, zorder=5))
    ax.add_patch(Rectangle((x_fl0 - hk, r_s - hd / 2), hk, hd, fc="#e0a100", ec="k", lw=0.5, zorder=5))
    nr, sr = redp["bolts"].split("x")
    hd2, hk2 = HEAD[sr]
    d2 = float(sr[1:])
    r_r = float(redp["pcd"]) / 2
    ax.add_patch(Rectangle((xb - 2 * d2, r_r - d2 / 2), x_ring1 - xb + 2 * d2, d2, fc="#c62828", ec="k", lw=0.5, zorder=5))
    ax.add_patch(Rectangle((x_ring1, r_r - hd2 / 2), hk2, hd2, fc="#c62828", ec="k", lw=0.5, zorder=5))
    ax.axhline(0, color=MUTE, lw=0.8, ls="-.")
    xs = [x for p in red + prt for x, _ in p["pts"]]
    ax.set_xlim(min(xs) - 12, max(xs) + 12)
    ax.set_ylim(-4, r_fl + 26)
    ax.set_aspect("equal")
    ax.tick_params(labelsize=7, colors=MUTE)
    for s in ax.spines.values():
        s.set_color("#c9cfd6")
    ax.grid(color="#eceff2", lw=0.5)
    title = (f"{j['name']}: {os.path.basename(j['use']['reducer']).split('.')[0]} + "
             f"{os.path.basename(j['use']['motor']).split('.')[0]}")
    ax.set_title(title, fontsize=10.5, color=INK, loc="left")
    txt = (f"фланец D{2 * r_fl:.0f}, звено: расточка D{2 * r_link:.0f}H7 по корпусу редуктора, {n} × {size} DIN912 на "
           f"D{2 * r_s:.0f}\nфланец → редуктор: {nr} × {sr} DIN912 на D{2 * r_r:.0f} со стороны выхода")
    ax.text(0.01, -0.13, txt, transform=ax.transAxes, fontsize=8.3, color=INK, va="top")


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    ap = argparse.ArgumentParser()
    ap.add_argument("joints", nargs="+")
    ap.add_argument("--png", default=os.path.join(ROOT, "joints", "joint-sections.png"))
    a = ap.parse_args()
    n = len(a.joints)
    cols = 2 if n > 1 else 1
    rows = (n + cols - 1) // cols
    fig, axs = plt.subplots(rows, cols, figsize=(8 * cols, 5.6 * rows), squeeze=False)
    for ax, p in zip(axs.ravel(), a.joints):
        draw(ax, p)
    for ax in axs.ravel()[n:]:
        ax.axis("off")
    leg = [Patch(fc="#2a5d9f", label="фланец + корпус двигателя"), Patch(fc="#f2e6c9", hatch="///", label="звено (предыдущее)"),
           Patch(fc="#e0a100", label="винты звено → фланец"), Patch(fc="#c62828", label="винты фланец → редуктор"),
           Patch(fc="#b8c2cc", label="корпус редуктора"), Patch(fc="#e3b36e", label="входной вал"),
           Patch(fc="#8fbf7f", label="выходной вал"), Patch(fc="#d98c5f", label="стакан ротора"),
           Patch(fc="#555b63", label="двигатель (контур)")]
    fig.legend(handles=leg, loc="upper left", bbox_to_anchor=(0.01, 0.975), ncol=5, frameon=False, fontsize=9)
    fig.suptitle("Шарниры с фланцем крепления к звену (полуразрез, мм)", fontsize=13, x=0.01, ha="left", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.92), h_pad=3)
    fig.savefig(a.png, dpi=130, facecolor="white")
    print("->", a.png)


if __name__ == "__main__":
    main()
