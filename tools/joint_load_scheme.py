#!/usr/bin/env python3
"""Load scheme of the arm: the whole RTC-7 (zero pose, as on the user's scheme) and, next to every joint,
the largest loads of the model against what its reducer gives in the rated duty (catalog).

    python tools/joint_load_scheme.py [--cases S P "A 0.5"] [--png robot/RTC-7-load-scheme.png]

Loads: robot/RTC-7-joint-compare.json (tools/joint_compare.py) - the max over the chosen cases
(S statics worst pose, P demo program at the rated speeds n0, A t start to n0 in t s). Rated: the reducer cards
(components/DMRD/*): T_rated (80E - T_design, preliminary), M_tilt, F_axial; the catalog gives no radial force.
J1: the arm stands on the ОПУ RU178G - tilt and axial load go to the bearing, checked by the static
equivalent load P0 = Fr + 2 M / Dp + 0.44 Fa against C0 (crossed rollers).
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_envelope as je  # noqa: E402
import robot_scheme as rs  # noqa: E402
import robot_statics as st  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OK, WARN, BAD, INK, MUTE, TRACK = "#2e8b57", "#e0a100", "#c62828", "#1b2026", "#5d6670", "#e6e9ed"
SIZE_RU = {"SHM-60": "ШМ-60", "SHM-150": "ШМ-150", "SHM-500": "ШМ-500", "SHM-1000": "ШМ-1000", "SHM-150m": "ШМ-150м"}


def rated(lay):
    out = []
    for a in lay["axes"]:
        jn = a["joint"].rstrip("m")
        j = je.read_joint(os.path.join(ROOT, "joints", jn, jn + ".txt"))
        path = j["use"]["reducer"]
        d = st.card_data(os.path.join(ROOT, path))
        name = os.path.splitext(os.path.basename(path))[0]
        f = lambda k: float(d[k]) if k in d and d[k] != "?" else None
        out.append({"reducer": name, "T": f("T_design") or f("T_rated"), "T_cat": f("T_rated"),
                    "T_design": f("T_design"), "Tss": f("T_startstop"), "Mt": f("M_tilt"), "Fa": f("F_axial")})
    return out


def opu():
    d = st.card_data(os.path.join(ROOT, "components", "ISKRA", "RU178G", "RU178G-UU-CC0-P5.txt"))
    return float(d["C0_kN"]) * 1e3, float(d["Dp"]) * 1e-3


def colour(p):
    return OK if p <= 80 else WARN if p <= 100 else BAD


def bar_row(ax, y, label, val, lim, unit, note=None, case=None):
    """one row: label, 'calc / rated', bar of the ratio (100 % mark)"""
    ax.text(0.03, y, label, fontsize=9.2, color=INK, va="center")
    if case:
        ax.text(0.305, y, case, fontsize=7.5, color=MUTE, va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.15", fc="#f1f3f5", ec="none"))
    if lim is None:
        ax.text(0.44, y, f"{val:.0f} {unit}", ha="right", fontsize=9.2, color=INK, va="center", fontweight="bold")
        ax.text(0.60, y, note or "в каталоге нет", fontsize=8.3, color=MUTE, va="center", style="italic")
        return
    p = 100 * val / lim
    ax.text(0.44, y, f"{val:.0f}", fontsize=9.2, color=colour(p), va="center", ha="right", fontweight="bold")
    ax.text(0.445, y, f" / {lim:.0f} {unit}", fontsize=9.2, color=INK, va="center")
    x0, w = 0.65, 0.22
    ax.add_patch(__import__("matplotlib").patches.Rectangle((x0, y - 0.028), w, 0.056, fc=TRACK, ec="none"))
    ax.add_patch(__import__("matplotlib").patches.Rectangle((x0, y - 0.028), w * min(p, 150) / 150, 0.056,
                                                            fc=colour(p), ec="none"))
    ax.plot([x0 + w / 1.5] * 2, [y - 0.05, y + 0.05], color=INK, lw=1)
    ax.text(x0 + w + 0.015, y, f"{p:.0f} %", fontsize=8.8, color=colour(p), va="center", fontweight="bold")


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import ConnectionPatch, FancyBboxPatch
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=os.path.join(ROOT, "robot", "RTC-7-layout.txt"))
    ap.add_argument("--loads", default=os.path.join(ROOT, "robot", "RTC-7-joint-compare.json"))
    ap.add_argument("--cases", nargs="+", default=["S", "P", "A 0.5"])
    ap.add_argument("--png", default=os.path.join(ROOT, "robot", "RTC-7-load-scheme.png"))
    a = ap.parse_args()
    lay = rs.read_layout(a.layout)
    J = json.load(open(a.loads, encoding="utf-8"))
    L = np.max([np.array(J["loads"][c]) for c in a.cases], axis=0)       # 7 x (Fa, Fr, Mtilt, T)
    which = np.argmax([np.array(J["loads"][c]) for c in a.cases], axis=0)
    R = rated(lay)
    C0, Dp = opu()
    req = J["req"]

    fig = plt.figure(figsize=(16.5, 13.5))
    ax = fig.add_axes([0.355, 0.03, 0.29, 0.86])
    rs.draw_side(ax, lay, title="")
    for t in ax.texts:                                           # Russian labels on the drawing
        s = t.get_text()
        for k, v in SIZE_RU.items():
            s = s.replace(" " + k, " " + v) if s.endswith(k) else s
        t.set_text(s.replace("flange (estimated)", "фланец").replace("flange", "фланец"))
    ax.set_title("")
    # joint centres (as draw_side places them)
    n = len(lay["axes"])
    pts, dirs, Tf = rs.fk_poe(lay, np.zeros(n))
    cen = rs.body_centres(lay, pts, dirs, Tf[:3, 3])
    bodies = rs.joint_bodies(lay)
    for i in range(n):
        if bodies[i]:
            cen[i] = np.mean([b[0] for b in bodies[i]], axis=0)
    # boxes: left column J2 J4 J6 (horizontal axes, motors to the left), right J1 J3 J5 J7
    W, H = 0.325, 0.2
    pos = {5: (0.012, 0.62), 3: (0.012, 0.36), 1: (0.012, 0.10),
           6: (0.663, 0.695), 4: (0.663, 0.475), 2: (0.663, 0.255), 0: (0.663, 0.02)}
    for i in range(n):
        x, y = pos[i]
        h = H if i != 0 else 0.215
        b = fig.add_axes([x, y, W, h])
        b.set_xlim(0, 1), b.set_ylim(0, 1), b.axis("off")
        r = R[i]
        worst = max(L[i, 3] / r["T"], L[i, 2] / r["Mt"] if (r["Mt"] and i) else 0)
        b.add_patch(FancyBboxPatch((0.005, 0.01), 0.99, 0.98, boxstyle="round,pad=0,rounding_size=0.03",
                                   fc="white", ec=colour(100 * worst), lw=2.2))
        b.text(0.03, 0.9, f"{lay['axes'][i]['name']}  {SIZE_RU[lay['axes'][i]['joint']]}", fontsize=12.5,
               fontweight="bold", color=INK, va="center")
        b.text(0.97, 0.9, f"редуктор {r['reducer']}", fontsize=9.5, color=MUTE, va="center", ha="right")
        b.text(0.03, 0.775, "нагрузка (расчёт, max)  /  редуктор (номинал по каталогу)", fontsize=8, color=MUTE,
               va="center")
        rows = 0.64
        dy = 0.135 if i else 0.112
        tnote = "" if r["T_design"] is None else f"  (кат. {r['T_cat']:.0f})"
        tag = lambda col: {"S": "S", "P": "P"}.get(a.cases[which[i, col]], "A")
        bar_row(b, rows, "Момент, Н·м", L[i, 3], r["T"], "", case=tag(3))
        if tnote:
            b.text(0.445, rows - 0.065, f" рабочий, предв.{tnote}", fontsize=7.2, color=MUTE, va="center")
        if i == 0:
            P0 = L[0, 1] + 2 * L[0, 2] / Dp + 0.44 * L[0, 0]
            bar_row(b, rows - dy, "Опрок. момент, Н·м", L[0, 2], None, "", "воспринимает ОПУ RU178G", tag(2))
            bar_row(b, rows - 2 * dy, "Осевая Fa, Н", L[0, 0], None, "", "воспринимает ОПУ RU178G", tag(0))
            bar_row(b, rows - 3 * dy, "Радиальная Fr, Н", L[0, 1], None, "", "воспринимает ОПУ RU178G", tag(1))
            bar_row(b, rows - 4 * dy, "ОПУ: P0 экв., Н", P0, C0, "")
            b.text(0.03, rows - 4 * dy - 0.07, f"P0 = Fr + 2M/Dp + 0,44Fa против C0; запас s0 = {C0 / P0:.1f}",
                   fontsize=7.4, color=MUTE, va="center")
        else:
            bar_row(b, rows - dy, "Опрок. момент, Н·м", L[i, 2], r["Mt"], "", case=tag(2))
            bar_row(b, rows - 2 * dy, "Осевая Fa, Н", L[i, 0], r["Fa"], "", "в каталоге нет", tag(0))
            bar_row(b, rows - 3 * dy, "Радиальная Fr, Н", L[i, 1], None, "", case=tag(1))
        b.text(0.03, 0.045 if i == 0 else 0.06, f"n0 = {req[i]['n0']:.0f} °/с;  пусковой момент редуктора {r['Tss']:.0f} Н·м "
                           f"({100 * L[i, 3] / r['Tss']:.0f} %)", fontsize=7.6, color=MUTE, va="center")
        # leader line from the box edge to the joint
        c = cen[i]
        left = x < 0.5
        con = ConnectionPatch(xyA=(1.0 if left else 0.0, 0.5), coordsA=b.transAxes, xyB=(c[0], c[2]),
                              coordsB=ax.transData, color=colour(100 * worst), lw=1.4, ls="-", zorder=20)
        fig.add_artist(con)
        ax.plot(c[0], c[2], "o", ms=7, mfc="white", mec=colour(100 * worst), mew=2, zorder=30)
    cases_ru = {"S": "статика, худшая из 20 000 поз", "P": "демо-программа на номинальных скоростях n0"}
    cs = "; ".join(cases_ru.get(c, f"разгон шарнира до n0 за {c.split()[-1].replace('.', ',')} с в худшей позе") for c in a.cases)
    fig.text(0.012, 0.975, "RTC-7: нагрузки шарниров и возможности редукторов в номинальном режиме", fontsize=17,
             fontweight="bold", color=INK, va="top")
    fig.text(0.012, 0.948, "Расчёт: обратная динамика, груз 8 кг + интерфейс 4 кг; силы и опрокидывающий момент — на торце "
             "выходного вала шарнира. Максимум из случаев:", fontsize=9.5, color=MUTE, va="top")
    tags = {"S": "S", "P": "P"}
    fig.text(0.012, 0.930, "   ".join(f"[{tags.get(c, 'A')}] {cases_ru.get(c, f'разгон шарнира до n0 за {c.split()[-1].replace(chr(46), chr(44))} с в худшей позе')}"
             for c in a.cases), fontsize=9.5, color=INK, va="top")
    fig.text(0.012, 0.912, "Номинал редуктора — каталог DMRD: номинальный момент T_rated, допустимый опрокидывающий "
             "момент M_tilt, допустимая осевая сила; радиальной силы в каталоге нет. Шкала полос — до 150 %, "
             "черта — 100 %.", fontsize=9.5, color=MUTE, va="top")
    for k, (cl, tx) in enumerate(((OK, "≤ 80 % номинала"), (WARN, "80…100 %"), (BAD, "> 100 % — превышение"))):
        fig.patches.append(__import__("matplotlib").patches.Rectangle((0.012 + k * 0.105, 0.06), 0.012, 0.012,
                                                                      fc=cl, transform=fig.transFigure, figure=fig))
        fig.text(0.027 + k * 0.105, 0.066, tx, fontsize=9.5, color=INK, va="center")
    fig.text(0.012, 0.035, "Схема — нулевая поза (вид вдоль +Y); точки — центры шарниров. Метка у значения — случай, "
             "дающий максимум.", fontsize=8.5, color=MUTE)
    fig.text(0.988, 0.006, "tools/joint_load_scheme.py · robot/RTC-7-joint-compare.json", fontsize=7.5, color=MUTE,
             ha="right")
    fig.savefig(a.png, dpi=150, facecolor="white")
    fig.savefig(os.path.splitext(a.png)[0] + ".pdf", facecolor="white")
    print("->", a.png)
    for i in range(n):
        print(lay["axes"][i]["name"], R[i]["reducer"], "T", round(L[i, 3]), "/", R[i]["T"], "Mt", round(L[i, 2]), "/",
              R[i]["Mt"], "Fa", round(L[i, 0]), "/", R[i]["Fa"], "Fr", round(L[i, 1]),
              "cases", [a.cases[w] for w in which[i]])


if __name__ == "__main__":
    main()
