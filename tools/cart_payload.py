"""Payload capacity map of the RTC-7 arm on the cart, top view (hull frame, platform/CART/CART.md).

Pose: SZU axis vertical down (as for the load "Груз 400"), the payload centre of mass PAY_COM mm below the TCP (centre of
the 400 cube), SZU 4 kg always on. Capacity = the largest payload with every joint at <= LIMIT of its allowed static
torque (tools/cart_reach.py CAP, TILT: min(reducer rated, motor rated x i x 0.8)); gravity only.

For one TCP height the arm configurations are found once per radius from the J1 axis (IK from many seeds, collisions
not checked); the torques depend on the radius only (J1 vertical), so a point of the map at the angle theta takes these
configurations turned by J1 and checks them against the cart, the ground and itself (FCL, the load cube attached).

    python tools/cart_payload.py [out_dir]      -> payload_map_<level>.png, payload_radius.png, payload_map.json
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cart_layout as cl, cart_reach as cr

LIMIT = 0.9                 # share of the allowed static torque (10 % left for the accelerations)
PAY_COM = 200.0             # mm below the TCP
LEVELS = {"ground": ("груз на грунте (TCP = верх куба 400, y = −197,5)", cl.GROUND_Y + 400.0),
          "deck": ("над палубой: низ груза на 600 мм, выше конусов (TCP y = 1000)", 1000.0),
          "transfer": ("высота переноса (TCP y = 1500)", 1500.0)}
# capacity bands (user 2026-11-12: more classes by mass, the max capacity of each zone); the calculation stops at 40 kg
BINS = [0, 8, 10, 12, 14, 16, 18, 20, 25, 30, 35, 39.99, 1e9]
def _blab(a, b):
    if a == 0: return f"< {b:g} кг"
    if b > 1e8: return "≥ 40 кг (предел расчёта)"
    return f"{a:g}–{round(min(b, 40)):g} кг"
BIN_LAB = [_blab(a, b) for a, b in zip(BINS[:-1], BINS[1:])]
def _bcol():
    import matplotlib
    cm = matplotlib.colormaps["RdYlGn"]; n = len(BINS) - 1
    return [matplotlib.colors.to_hex(cm(0.04 + 0.92 * i / (n - 1))) for i in range(n)]
BIN_COL = _bcol()
J1C = np.array([cl.FLANGE_C[0], cl.FLANGE_C[1]])           # flange / J1 axis, (x, z)

def capacity(arm, q, tcp):
    """largest payload, kg (0..40), for the pose q; tcp - the TCP point in the hull (payload COM below it)."""
    com = np.asarray(tcp, float) + np.array([0, -PAY_COM, 0])
    def worst(m):
        cr.LOAD_KG = m
        tq, tilt, r = cr.ratio(arm, q, com)
        return max(r.values())
    if worst(0.0) > LIMIT: return 0.0
    lo, hi = 0.0, 40.0
    if worst(hi) <= LIMIT: return hi
    for _ in range(18):
        mid = (lo + hi) / 2
        if worst(mid) <= LIMIT: lo = mid
        else: hi = mid
    return lo

def radial_solutions(arm, y, radii, sc=None, box_rel=None, theta0=math.radians(45), nseed=40, keep=12):
    """for every radius: [(capacity, q)] of distinct IK solutions with the TCP at (r, theta0) around J1, height y;
    theta0 looks away from the cart (rear-outward), so with sc given only solutions free of self-contacts (arm / the
    load in the gripper) are kept. Seeds: random + elbow-up / elbow-down families + the scenario poses."""
    rng = np.random.default_rng(5)
    seeds = [rng.uniform(-math.pi, math.pi, 7) * np.array([1, 0.9, 0.3, 1, 0.3, 1, 1]) for _ in range(nseed)]
    for q2 in (-70, -40, -10, 20):
        for q4 in (40, 80, 120, -40, -80, -120):
            seeds.append(np.radians([0, q2, 0, q4, 0, -(q2 + q4) - 90 if q4 > 0 else -(q2 + q4) + 90, 0]))
    try:
        R = json.load(open(os.path.join(cl.ROOT, "platform/CART/reach_scen.json")))
        seeds += [np.array(v) for k in ("q_lift", "q_far", "q_near") for v in R[k]]
    except Exception:
        pass
    out = {}; prev = []
    for r in radii:
        p = np.array([J1C[0] + r * math.cos(theta0), y, J1C[1] + r * math.sin(theta0)])
        sols = []
        for s in prev + seeds:
            q, e, an = arm.ik(p, cr.DOWN, s)
            if e > 0.5 or an > 0.2: continue
            if any(np.abs(((q - x[1] + math.pi) % (2 * math.pi)) - math.pi).max() < 0.05 for x in sols): continue
            if sc is not None and (sc.pairs(q, box_rel) or not ground_ok(arm, q)): continue
            sols.append((capacity(arm, q, arm.tcp(q)[0]), q))
        sols.sort(key=lambda x: -x[0]); out[float(r)] = sols[:keep]
        prev = [x[1] for x in sols[:6]]
    return out

def turn_q(q, dth):
    q = q.copy(); q[0] += dth; return q

def ground_ok(arm, q, margin=5.0):
    Tg, cum = arm.fk(q)
    for g, t in arm.groups.items():
        if g in ("B", "J1"): continue
        M = cl.ROBOT @ Tg[g]
        if (t.reshape(-1, 3)[::3] @ M[:3, :3].T + M[:3, 3])[:, 1].min() < cl.GROUND_Y + margin: return False
    return True

def topview_map(arm, sc, sols, box_rel, step=60.0):
    rmax = max(r for r, s in sols.items() if s)
    xs = np.arange(J1C[0] - rmax - step, J1C[0] + rmax + step, step)
    zs = np.arange(J1C[1] - rmax - step, J1C[1] + rmax + step, step)
    R = sorted(sols); Ra = np.array(R)
    cap = np.full((len(zs), len(xs)), np.nan)      # nan - out of reach; -1 - reachable only with a contact
    for iz, z in enumerate(zs):
        for ix, x in enumerate(xs):
            r = math.hypot(x - J1C[0], z - J1C[1])
            if r > rmax + 1: continue
            k = int(np.argmin(np.abs(Ra - r)))
            if abs(Ra[k] - r) > step or not sols[R[k]]: continue
            th = math.atan2(z - J1C[1], x - J1C[0]) - math.radians(45)
            res = -1.0
            for c, q in sols[R[k]]:
                qq = turn_q(q, -th)          # J1 turns about +Y: the hull angle (x -> z) goes the other way
                p = arm.tcp(qq)[0]
                if math.hypot(p[0] - x, p[2] - z) > step: qq = turn_q(q, th); p = arm.tcp(qq)[0]
                if sc.pairs(qq, box_rel) or not ground_ok(arm, qq): continue
                res = max(res, c); break     # solutions are sorted by capacity
            cap[iz, ix] = res
    return xs, zs, cap

def outline(ax):
    """cart silhouette in the top view (projected triangles of the models)."""
    import link_build as lb
    from matplotlib.collections import PolyCollection
    cache = {}; COL = {"hull": "#9aa3a8", "wheel": "#4a4d50", "panel": "#3d6fae"}
    for n, f, M, c in cl.cart_parts():
        if f not in cache: cache[f] = np.array(lb.triangles(cl.load_step(os.path.join(cl.CART_DIR, f)), 6.0))
        t = cache[f] @ M[:3, :3].T + M[:3, 3]
        ax.add_collection(PolyCollection(t[:, :, [0, 2]], facecolors=COL.get(n, c), edgecolors="none", alpha=0.45 if n == "panel" else 0.6, zorder=2))

HULL_FOOT = (0.0, 2659.0, -730.0, 730.0)   # hull box in the top view (x0, x1, z0, z1): the ground under it is not a work zone

def mask_under_hull(xs, zs, cap):
    """ground level: the points under the hull box -> out of the map. The hull model has no floor under the open rear
    bay (x ~1820..2640), so the arm passes through it in the model; under a real cart that is not a work zone."""
    c = cap.copy(); X, Z = np.meshgrid(xs, zs)
    c[(X >= HULL_FOOT[0]) & (X <= HULL_FOOT[1]) & (Z >= HULL_FOOT[2]) & (Z <= HULL_FOOT[3])] = np.nan
    return c

MONO_R = 700.0      # beyond this radius the capacity can only fall with the radius (static moments grow)

def smooth_cap(xs, zs, cap, R, C):
    """the map without the IK seed scatter: the best capacity found at a radius r is also reachable closer in
    (r >= MONO_R), so the radial curve becomes its outer envelope; a cell keeps its own loss against the best
    configuration at its radius (contacts with the cart force a weaker configuration there)."""
    R = np.asarray(R, float); C = np.asarray(C, float)
    env = C.copy()
    for i in range(len(R) - 2, -1, -1):
        if R[i] >= MONO_R: env[i] = max(env[i], env[i + 1])
    X, Z = np.meshgrid(xs, zs); Rg = np.hypot(X - J1C[0], Z - J1C[1])
    top = np.interp(Rg, R, C); en = np.interp(Rg, R, env)
    out = np.where(cap >= 0, np.minimum(40.0, en - np.maximum(0.0, top - cap)), cap)
    return out, R, env

def zones(R, env, rmax):
    """[(band label, r_from, r_to, largest capacity in it, colour)] - rings of the envelope from the J1 axis outward."""
    rows = []
    for k, (a, b) in enumerate(zip(BINS[:-1], BINS[1:])):
        m = (env >= a) & (env < b) & (R >= MONO_R)
        if not m.any(): continue
        rows.append((BIN_LAB[k], float(R[m].min()), float(min(R[m].max() + 25, rmax)), float(env[m].max()), BIN_COL[k]))
    rows.sort(key=lambda r: r[1])
    return rows

def draw(level, title, xs, zs, cap, sols, png, r_any, R=None, C=None):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch, Circle
    rmax = sols if isinstance(sols, (int, float)) else max(r for r, s in sols.items() if s)
    if R is None: R = sorted(r for r in sols if sols[r]); C = [sols[r][0][0] for r in R]
    capS, Ra, env = smooth_cap(xs, zs, cap, R, C)
    fig = plt.figure(figsize=(19, 11.5)); ax = fig.add_axes([0.05, 0.07, 0.62, 0.86]); tx = fig.add_axes([0.69, 0.07, 0.30, 0.86]); tx.axis("off")
    cm = ListedColormap(BIN_COL); norm = BoundaryNorm(BINS[:-1] + [100], cm.N)
    c2 = np.where(capS >= 0, capS, np.nan)
    ext = (xs[0] - 30, xs[-1] + 30, zs[-1] + 30, zs[0] - 30)
    outline(ax)
    ax.imshow(c2, extent=ext, cmap=cm, norm=norm, origin="upper", alpha=0.72, zorder=4, interpolation="nearest")
    X, Z = np.meshgrid(xs, zs)
    cs = ax.contour(X, Z, np.where(np.isnan(c2), -5, c2), levels=[b for b in BINS[1:-1]], colors="#222", linewidths=0.6, zorder=5)
    ax.clabel(cs, fmt=lambda v: f"{v:.0f}" if v < 39 else "40", fontsize=8, inline=True)
    hit = np.where(capS == -1, 1.0, np.nan)
    ax.imshow(hit, extent=ext, cmap=ListedColormap(["#8f8fa8"]), origin="upper", alpha=0.55, zorder=4, interpolation="nearest")
    for r in range(500, 3001, 500):
        ax.add_patch(Circle(J1C, r, fill=False, lw=0.8, ls="--", color="#333", zorder=4))
        ax.text(J1C[0] + r * 0.707 + 15, J1C[1] - r * 0.707 - 15, f"R{r}", fontsize=9, color="#222", zorder=5)
    ax.add_patch(Circle(J1C, rmax, fill=False, lw=2.0, color="#1f4e8c", zorder=5))
    ax.add_patch(Circle(J1C, r_any, fill=False, lw=1.6, ls="-.", color="#7b2d8e", zorder=5))
    for nm, (sx, sy, sz) in cl.SEATS.items():
        ax.plot(sx, sz, "o", ms=9, mfc="white", mec="k", zorder=6)
        ax.text(sx + 60, sz - 60, "дальнее место" if nm == "far" else "ближнее место", fontsize=9, zorder=6)
    gx, gz = cr.BOX_GROUND
    ax.add_patch(plt.Rectangle((gx - 200, gz - 200), 400, 400, fill=False, lw=1.4, ec="k", zorder=6))
    ax.text(gx - 190, gz - 220, "груз 400 на грунте", fontsize=9, zorder=6)
    ax.plot(*J1C, "k+", ms=14, mew=2, zorder=6); ax.text(J1C[0] + 40, J1C[1] + 90, "ось J1", fontsize=9, zorder=6)
    ax.set_aspect("equal"); ax.set_xlim(min(xs[0], -400), max(xs[-1], 3000)); ax.set_ylim(max(zs[-1], 1100), min(zs[0], -2100))
    ax.set_xlabel("X вдоль тележки, мм (0 — передний торец)"); ax.set_ylabel("Z поперёк, мм (+Z — борт робота)")
    ax.grid(alpha=0.25)
    fig.suptitle(f"RTC-7 на тележке: грузоподъёмность, вид сверху — {title}", fontsize=13, x=0.36, y=0.985)
    # zone table
    rows = zones(Ra, env, rmax)
    tx.text(0, 1.0, "Зоны грузоподъёмности", fontsize=13, weight="bold", va="top")
    tx.text(0, 0.965, "кольца от оси J1; макс. груз в зоне — на её внутренней границе", fontsize=9.5, va="top", color="#444")
    y = 0.92
    tx.text(0.02, y, "груз, кг", fontsize=10, weight="bold"); tx.text(0.42, y, "радиус от оси J1, мм", fontsize=10, weight="bold")
    tx.text(0.80, y, "макс., кг", fontsize=10, weight="bold"); y -= 0.035
    inner = [r for r, c in zip(Ra, C) if r < MONO_R]
    if inner:
        cin = [c for r, c in zip(Ra, C) if r < MONO_R]
        tx.add_patch(plt.Rectangle((0, y - 0.008), 1, 0.03, color="#eee", transform=tx.transAxes))
        tx.text(0.02, y, f"{min(cin):.0f}…{max(cin):.0f}", fontsize=10); tx.text(0.42, y, f"R{min(inner):.0f}…R{MONO_R:.0f}", fontsize=10)
        tx.text(0.80, y, f"{max(cin):.0f}", fontsize=10); tx.text(0.99, y + 0.022, "у оси J1: рука сложена", fontsize=7.5, color="#555", ha="right"); y -= 0.035
    for lab, r0, r1, cmax, col in rows:
        tx.add_patch(plt.Rectangle((0, y - 0.008), 1, 0.03, color=col, alpha=0.8, transform=tx.transAxes))
        tx.text(0.02, y, lab.replace(" кг", ""), fontsize=10); tx.text(0.42, y, f"R{r0:.0f}…R{r1:.0f}", fontsize=10)
        tx.text(0.80, y, "≥ 40" if cmax >= 39.99 else f"{cmax:.1f}", fontsize=10); y -= 0.035
    y -= 0.02
    notes = [f"СЗУ вертикально вниз, центр масс груза в {PAY_COM:.0f} мм под TCP, СЗУ 4 кг учтён;",
             f"все шарниры ≤ {LIMIT*100:.0f} % допускаемого момента (статика, 10 % — на разгон);",
             "грузоподъёмность рассчитана до 40 кг.",
             f"граница досягаемости на этой высоте — R{rmax:.0f}; предельный вылет TCP — R{r_any:.0f}.",
             "Цвет — грузоподъёмность клетки 60 × 60 мм; у бортов и колёс она ниже кольца:",
             "там рука обходит тележку менее выгодной позой."]
    for t in notes: tx.text(0, y, t, fontsize=9, color="#333", va="top"); y -= 0.028
    y -= 0.01
    h = [Patch(color="#8f8fa8", alpha=0.55, label="достаёт, но рука или груз задевает тележку / грунт"),
         Patch(facecolor="white", edgecolor="#999", label="без цвета — не достаёт" + (" / под корпусом" if level == "ground" else "")),
         plt.Line2D([], [], color="#1f4e8c", lw=2, label="граница досягаемости на этой высоте"),
         plt.Line2D([], [], color="#7b2d8e", lw=1.6, ls="-.", label="предельный вылет TCP (любая ориентация)"),
         plt.Line2D([], [], color="#333", lw=0.8, ls="--", label="окружности от оси J1 через 500 мм"),
         plt.Line2D([], [], color="#222", lw=0.6, label="границы зон (подписи — кг)")]
    tx.legend(handles=h, loc="upper left", bbox_to_anchor=(0, y), fontsize=9, frameon=False)
    plt.savefig(png, dpi=105); plt.close(fig)
    return rows

def radius_png(curves, png, r_any):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for lev, (R, C) in curves.items():
        ax.plot(R, C, lw=2, label=LEVELS[lev][0])
    for b in BINS[1:-1]: ax.axhline(b, color="#999", lw=0.6, ls=":")
    ax.axhline(8, color="#c0392b", lw=1, ls="--"); ax.text(60, 8.3, "груз 8 кг", color="#c0392b", fontsize=9)
    ax.axvline(r_any, color="#7b2d8e", lw=1, ls="-.")
    ax.set_xlabel("расстояние от оси J1 до TCP по горизонтали, мм"); ax.set_ylabel("грузоподъёмность, кг")
    ax.set_title(f"Грузоподъёмность от вылета (без учёта тележки), шарниры ≤ {LIMIT*100:.0f} % допускаемого, статика")
    ax.set_ylim(0, 40); ax.grid(alpha=0.3); ax.legend(); plt.tight_layout(); plt.savefig(png, dpi=110); plt.close(fig)

def main(out_dir):
    arm = cr.Arm(); sc = cr.Scene(arm, box_at=None)
    box_rel = np.array(json.load(open(os.path.join(cl.ROOT, "platform/CART/reach_scen.json")))["box_rel"])
    # limit of the TCP reach (any orientation): J2 axis -> TCP fully stretched, + the lateral offset
    j2 = (cl.ROBOT @ np.r_[arm.axes[1][0], 1])[:3]; j4 = arm.axes[3][0]; j6 = arm.axes[5][0]
    L = (j4[0] - arm.axes[1][0][0]) + (j6[0] - j4[0]) + (arm.tcp0[0] - j6[0])
    r_any = math.hypot(L, 215.5)
    radii = np.arange(0, 2801, 25.0)
    out = {"limit": LIMIT, "pay_com": PAY_COM, "r_any": r_any, "levels": {}}; curves = {}
    for lev, (title, y) in LEVELS.items():
        sols = radial_solutions(arm, y, radii, sc, box_rel)
        R = [r for r in sols if sols[r]]; C = [sols[r][0][0] for r in R]; curves[lev] = (R, C)
        print(lev, "max radius", max(R), "capacity at R1000/1500/2000:",
              [round(sols[r][0][0], 1) if sols.get(r) else None for r in (1000.0, 1500.0, 2000.0)], flush=True)
        xs, zs, cap = topview_map(arm, sc, sols, box_rel)
        if lev == "ground": cap = mask_under_hull(xs, zs, cap)
        draw(lev, title, xs, zs, cap, sols, os.path.join(out_dir, f"payload_map_{lev}.png"), r_any)
        out["levels"][lev] = {"title": title, "y": y, "radius": R, "capacity": [round(c, 2) for c in C],
                              "x": xs.tolist(), "z": zs.tolist(), "cap": np.where(np.isnan(cap), None, np.round(cap, 1)).tolist()}
        json.dump(out, open(os.path.join(out_dir, "payload_map.json"), "w"), ensure_ascii=False)
    radius_png(curves, os.path.join(out_dir, "payload_radius.png"), r_any)

def one_level(out_dir, lev):
    """recompute one level of payload_map.json (the others kept)."""
    arm = cr.Arm(); sc = cr.Scene(arm, box_at=None)
    box_rel = np.array(json.load(open(os.path.join(cl.ROOT, "platform/CART/reach_scen.json")))["box_rel"])
    D = json.load(open(os.path.join(out_dir, "payload_map.json"), encoding="utf-8"))
    title, y = LEVELS[lev]; sols = radial_solutions(arm, y, np.arange(0, 2801, 25.0), sc, box_rel)
    R = [r for r in sols if sols[r]]; xs, zs, cap = topview_map(arm, sc, sols, box_rel)
    D["levels"][lev] = {"title": title, "y": y, "radius": R, "capacity": [round(sols[r][0][0], 2) for r in R],
                        "x": xs.tolist(), "z": zs.tolist(), "cap": np.where(np.isnan(cap), None, np.round(cap, 1)).tolist()}
    json.dump(D, open(os.path.join(out_dir, "payload_map.json"), "w"), ensure_ascii=False)
    redraw(out_dir)

def redraw(out_dir):
    """the pictures again from payload_map.json (no IK / collision runs)."""
    D = json.load(open(os.path.join(out_dir, "payload_map.json"), encoding="utf-8")); curves = {}
    for lev, L in D["levels"].items():
        xs, zs = np.array(L["x"]), np.array(L["z"])
        cap = np.array([[np.nan if v is None else v for v in r] for r in L["cap"]], float)
        if lev == "ground": cap = mask_under_hull(xs, zs, cap)
        rows = draw(lev, L["title"], xs, zs, cap, float(max(L["radius"])), os.path.join(out_dir, f"payload_map_{lev}.png"), D["r_any"],
                    L["radius"], L["capacity"])
        print(lev, [(r[0], round(r[1]), round(r[2]), round(r[3], 1)) for r in rows])
        curves[lev] = (L["radius"], L["capacity"])
    radius_png(curves, os.path.join(out_dir, "payload_radius.png"), D["r_any"])

if __name__ == "__main__":
    if sys.argv[1:2] == ["level"]: one_level(os.path.join(cl.ROOT, "platform/CART"), sys.argv[2])
    elif sys.argv[1:2] == ["redraw"]: redraw(sys.argv[2] if len(sys.argv) > 2 else os.path.join(cl.ROOT, "platform/CART"))
    else: main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(cl.ROOT, "platform/CART"))
