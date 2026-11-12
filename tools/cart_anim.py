"""Viewer of the RTC-7 arm on the wheeled cart (HTML, three.js): the scenarios of platform/CART/REACH.md.

    python tools/cart_anim.py [--html platform/CART/RTC-7-cart-viewer.html] [--offline <three@0.147.0 package dir>]

Programs = joint-space waypoints (tools/cart_reach.py results: platform/CART/reach_scen.json, reach_panel.json),
quintic blend per segment, durations from 0.2 rad/s and 0.1 rad/s² (the load model limits). Every 0.25 s of
every program the arm (+ load) is checked against the cart and itself (FCL) - the viewer shows the result.
"""
import sys, os, math, json, base64, argparse
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cart_layout as cl, cart_reach as cr

ROOT = cl.ROOT
VMAX, AMAX, DWELL = 0.2, 0.1, 1.5
# transport pose (user 2026-11-06, from the viewer pictures): J1 -93.5, J2 -90, J4 -180, J5 90, J6 -180 - the folded
# arm lies along the long side (X) to the front, the SZU across the cart standing up; x 1005..2477, z 426..945, top y 940
FOLD_J1 = [-93.5, 0, 0, 0, 0, 0, 0]          # deg
FOLD_WRIST = [-93.5, 0, 0, -180, 90, -180, 0]
FOLD = [-93.5, -90, 0, -180, 90, -180, 0]

def b64(a): return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")

def indexed(tri):
    v = tri.reshape(-1, 3).astype(np.float32)
    u, inv = np.unique(np.round(v, 2), axis=0, return_inverse=True)
    return u.astype(np.float32), inv.reshape(-1).astype(np.uint32)

def seg_T(q0, q1):
    d = float(np.max(np.abs(np.asarray(q1) - np.asarray(q0)))) if q0 is not None else 0.0
    if d < 1e-6: return DWELL
    return max(1.875 * d / VMAX, math.sqrt(5.7735 * d / AMAX), 1.5)

def unwrap(q0, q1):
    return q0 + ((np.asarray(q1) - q0 + math.pi) % (2 * math.pi) - math.pi)

class Checker:
    def __init__(self, arm):
        self.arm = arm
        self.scA = cr.Scene(arm, box_at=cr.BOX_GROUND)
        self.scB = cr.Scene(arm, box_at=None); self.scB.allowed = self.scA.allowed
        import fcl
        self.box_static = fcl.CollisionObject(cr.fcl_local(self.scB.box_local))
    def hits(self, q, state, box_rel, az, box_M=None, seat_contact=False):
        import fcl
        sc = self.scA if state == "ground" else self.scB
        if az is not None and getattr(sc, "_az", None) != az: sc.set_panel(az); sc._az = az
        skip = {("F", "box")}
        h = sc.pairs(q, box_rel if state == "held" else None, skip=skip)
        if seat_contact: h = [x for x in h if x != ("LOAD", "hull")]
        if state.startswith("at:") and box_M is not None:
            cr.set_tf(self.box_static, box_M)
            for g, o in sc.arm_obj.items():
                if g == "F": continue
                r = fcl.CollisionResult()
                if fcl.collide(o, self.box_static, fcl.CollisionRequest(), r): h.append((g, "box"))
        return h

NAMES = {"B": "пластина", "J1": "J1", "L1": "звено 1", "J2": "J2", "L2": "звено 2", "J3": "J3", "L3": "звено 3", "J4": "J4",
         "L4": "звено 4", "J5": "J5", "L5": "звено 5", "J6": "J6", "L6": "звено 6", "J7": "J7", "F": "СЗУ", "LOAD": "груз",
         "hull": "корпус", "wheel": "колесо", "panel": "панель", "box": "груз"}

def q_at(s, w):
    """joint position of segment s at the blend w (0..1): straight in joint space, or along its sampled path."""
    if "path" in s:
        P = np.array(s["path"]); x = w * (len(P) - 1); i = min(int(x), len(P) - 2); f = x - i
        return P[i] + f * (P[i + 1] - P[i])
    return np.array(s["q0"]) + w * (np.array(s["q1"]) - np.array(s["q0"]))

def path_T(P):
    """duration of a path segment (quintic blend over the index): the peak index rate x the largest joint step
    <= VMAX, and the travel / acceleration bound of seg_T."""
    P = np.array(P); n = len(P) - 1
    step = float(np.abs(np.diff(P, axis=0)).max())          # rad per index step
    d = float(np.abs(np.diff(P, axis=0)).sum(axis=0).max())  # the largest joint travel
    return max(1.875 * n * step / VMAX, math.sqrt(5.7735 * d / AMAX))

PATH_STEP = 10.0     # mm between the Cartesian samples

def resample(P, n=None):
    """the path again with equal joint-space steps (the largest joint moves alike between the samples): a uniform
    blend then runs every joint at an even rate - slow only where the arm must turn fast, not along the whole path."""
    P = np.array(P); d = np.abs(np.diff(P, axis=0)).max(axis=1); c = np.r_[0, np.cumsum(d)]
    if c[-1] < 1e-9: return [P[0], P[-1]]
    n = n or max(2, len(P)); t = np.linspace(0, c[-1], n)
    return [np.array([np.interp(x, c, P[:, k]) for k in range(P.shape[1])]) for x in t]

def vertical_path(arm, q0, a, b):
    """TCP along the straight a -> b with the SZU axis vertical (down): [q] from q0, one per PATH_STEP."""
    n = int(np.linalg.norm(np.asarray(b) - np.asarray(a)) / PATH_STEP) + 2
    Q = [np.asarray(q0, float)]
    for t in np.linspace(0, 1, n)[1:]:
        p = np.asarray(a) + (np.asarray(b) - np.asarray(a)) * t
        q, e, an = arm.ik(p, cr.DOWN, Q[-1], w_a=3000, reg=0.05)
        q = unwrap(Q[-1], q)
        if e > 0.5 or an > 0.05: raise RuntimeError(f"vertical path: no IK at {np.round(p)} ({e:.2f} mm, {an:.2f} deg)")
        Q.append(q)
    return Q

def build_program(name, wps, arm, chk, box_rel, dt=0.25):
    """wps: [(q, az, box_state, label)] - segment i goes from wps[i] to wps[i+1] with the state / label of wps[i+1]."""
    segs = []; q_prev = np.asarray(wps[0][0], float)
    box_at = {}
    for wa, wb in zip(wps[:-1], wps[1:]):
        (qa, aza, _, _), (qb, azb, st, lab) = wa[:4], wb[:4]
        path = wb[4] if len(wb) > 4 else None
        q0 = q_prev
        if path is not None:                              # Cartesian path (SZU axis vertical): joint samples
            P = [q0]
            for q in path[1:]: P.append(unwrap(P[-1], q))
            P = resample(P); q1 = P[-1]; q_prev = q1
            T = max(path_T(P), 1.5)
            segs.append({"q0": q0.tolist(), "q1": q1.tolist(), "T": round(T, 2), "az0": aza, "az1": azb, "box": st,
                         "label": lab, "path": [np.round(x, 6).tolist() for x in P]})
            continue
        q1 = unwrap(q0, qb); q_prev = q1
        T = max(seg_T(q0, q1), abs(azb - aza) / 6.0 if azb != aza else 0)       # panel turn 6 deg/s
        segs.append({"q0": q0.tolist(), "q1": q1.tolist(), "T": round(T, 2), "az0": aza, "az1": azb, "box": st, "label": lab})
    # box poses after the release: the TCP frame at the release x the load in the gripper
    for i, s in enumerate(segs):
        if s["box"].startswith("at:") and s["box"][3:] not in box_at:
            qr = np.array(segs[i - 1]["q1"]); M = cl.ROBOT @ arm.fk(qr)[1][7] @ box_rel
            box_at[s["box"][3:]] = M
    total = sum(s["T"] for s in segs); checks = []; n_bad = 0
    for k in range(int(total / dt) + 1):
        tt = k * dt; acc = 0
        for s in segs:
            if tt <= acc + s["T"] or s is segs[-1]: break
            acc += s["T"]
        u = min(1, max(0, (tt - acc) / s["T"])); w = u ** 3 * (10 - 15 * u + 6 * u * u)
        q = q_at(s, w); az = s["az0"] + w * (s["az1"] - s["az0"])
        tcp = arm.tcp(q)[0]
        seat_contact = s["box"] == "held" and tcp[1] < 923 + 12 and s["label"].startswith("установка")
        h = chk.hits(q, s["box"], box_rel, az, box_at.get(s["box"][3:]) if s["box"].startswith("at:") else None, seat_contact)
        txt = ", ".join(sorted({f"{NAMES.get(a, a)} / {NAMES.get(b, b)}" for a, b in h}))
        checks.append(txt); n_bad += bool(txt)
    print(f"{name}: {len(segs)} segments, {total:.1f} s, samples with contacts: {n_bad}/{len(checks)}",
          sorted({c for c in checks if c})[:6])
    return {"name": name, "segs": segs, "dt": dt, "checks": checks,
            "box_at": {k: M.tolist() for k, M in box_at.items()}}

# end of the transfer (TCP y over the seat): the far seat is approached descending - level at 1400 the arm is nearly
# stretched there (J4 ~ 0, the J3 / J5 axes align) and the vertical SZU makes J3 / J5 spin; 1150 keeps it bent
TRANSFER_END = {"far": 1150.0, "near": None}

def lift_place(arm, R, seat, chk, box_rel):
    """user 2026-11-12: the SZU axis vertical all the time the load is handled (the cube orientation does not matter):
    the grasp, the lift, the transfer and the placing go along straight TCP lines, solved every 10 mm."""
    q1, q2, q3 = [np.array(v) for v in R["q_lift"]]
    top = cl.box_top(cr.BOX_GROUND); st = cl.box_top(seat)
    ty = R.get(f"transit_{seat}", cr.TRANSIT); ye = TRANSFER_END[seat] or ty
    up = np.array([0, 1.0, 0])
    p1 = top + 150 * up; p2 = top; p3 = top + 500 * up; pa = np.array([top[0], ty, top[2]])
    pb = np.array([st[0], ye, st[2]]); p4 = st + 150 * up; p5 = st + 2 * up
    P12 = vertical_path(arm, q1, p1, p2); qg = P12[-1]
    P23 = vertical_path(arm, qg, p2, p3); P3a = vertical_path(arm, P23[-1], p3, pa)
    Pab = vertical_path(arm, P3a[-1], pa, pb); Pb4 = vertical_path(arm, Pab[-1], pb, p4)
    P45 = vertical_path(arm, Pb4[-1], p4, p5); q5 = P45[-1]
    P56 = vertical_path(arm, q5, p5, p4); q6 = P56[-1]
    z = np.zeros(7); s_ = "ближнему" if seat == "near" else "дальнему"
    W = [(z, 0, "ground", "исходная поза"),
         (q1, 0, "ground", "подход: СЗУ над штырём груза (+150 мм), ось СЗУ вертикальна"),
         (qg, 0, "ground", "надевание СЗУ на штырь до касания грани куба", P12),
         (qg, 0, "held", "фиксация груза"),
         (P23[-1], 0, "held", "подъём на 500 мм (ось СЗУ вертикальна)", P23),
         (P3a[-1], 0, "held", f"подъём на высоту переноса (TCP {ty:.0f})", P3a),
         (Pab[-1], 0, "held", f"перенос к {s_} посадочному месту" + (f", снижаясь до TCP {ye:.0f}" if ye != ty else ""), Pab),
         (Pb4[-1], 0, "held", "опускание: груз в 150 мм над конусом", Pb4),
         (q5, 0, "held", "установка на посадочное место", P45),
         (q5, 0, "at:" + seat, "освобождение груза"),
         (q6, 0, "at:" + seat, "отвод СЗУ вверх", P56),
         (z, 0, "at:" + seat, "исходная поза")]
    return W

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--html", default=os.path.join(ROOT, "platform/CART/RTC-7-cart-viewer.html"))
    ap.add_argument("--offline"); ap.add_argument("--panel-program", default=os.path.join(ROOT, "platform/CART/reach_panel_program.json"))
    a = ap.parse_args()
    arm = cr.Arm(); chk = Checker(arm)
    R = json.load(open(os.path.join(ROOT, "platform/CART/reach_scen.json"), encoding="utf-8"))
    box_rel = np.array(R["box_rel"])
    progs = [build_program("Груз → дальнее место", lift_place(arm, R, "far", chk, box_rel), arm, chk, box_rel),
             build_program("Груз → ближнее место", lift_place(arm, R, "near", chk, box_rel), arm, chk, box_rel)]
    # folding for transport (STATUS item 14; user 2026-11-05: parallel to the long side): J1 first (upright arm), then the
    # wrist (J4 / J5 / J6 with J2 = 0 - all joints at once hit the panel and the hull), then J2; unfolding in reverse
    z = np.zeros(7); q1 = np.radians(FOLD_J1); qw = np.radians(FOLD_WRIST); qf = np.radians(FOLD)
    progs.append(build_program("Складывание для транспортировки", [
        (z, 0, "none", "исходная поза"),
        (q1, 0, "none", "поворот J1 на −93,5°: рука вдоль длинного борта"),
        (qw, 0, "none", "складывание кисти: J4 −180°, J5 90°, J6 −180°"),
        (qf, 0, "none", "складывание плеча: J2 −90° — транспортное положение"),
        (qf, 0, "none", "транспортное положение: параллельно длинному борту"),
        (qw, 0, "none", "раскладывание плеча"),
        (q1, 0, "none", "раскладывание кисти"),
        (z, 0, "none", "исходная поза")], arm, chk, box_rel))
    if os.path.exists(a.panel_program):
        PP = json.load(open(a.panel_program, encoding="utf-8"))
        W = [(np.array(q), az, "none", lab) for q, az, lab in PP["wps"]]
        progs.append(build_program(PP["name"], W, arm, chk, box_rel))
    meshes = []
    for g, tri in arm.groups.items():
        v, i = indexed(tri @ cl.ROBOT[:3, :3].T + cl.ROBOT[:3, 3])
        meshes.append({"name": g, "kind": "arm", "nmov": cr.NMOV[g], "color": cl.ARM_COL.get(g, "#b8c2cc"), "pos": b64(v), "idx": b64(i)})
    import link_build as lb
    cache = {}; COL = {"hull": "#9aa3a8", "wheel": "#4a4d50", "panel": "#3d6fae"}
    for k, (n, f, M, c) in enumerate(cl.cart_parts()):
        if f not in cache: cache[f] = np.array(lb.triangles(cl.load_step(os.path.join(cl.CART_DIR, f)), 2.5))
        v, i = indexed(cache[f] @ M[:3, :3].T + M[:3, 3])
        meshes.append({"name": f"{n}{k}", "kind": "panel" if n == "panel" else "cart", "color": COL.get(n, c), "pos": b64(v), "idx": b64(i)})
    v, i = indexed(chk.scB.box_local)
    meshes.append({"name": "box", "kind": "box", "color": "#c9a24a", "pos": b64(v), "idx": b64(i)})
    H = cl.ROBOT
    axes = [[(H @ np.r_[o, 1])[:3].round(3).tolist(), (H[:3, :3] @ d).round(6).tolist()] for o, d in arm.axes]
    caps = [[f"J{k}", k, round(min(cr.CAP[k]), 1), "tq"] for k in range(1, 7)] + [[f"J{k}⊥", k, cr.TILT[k], "tilt"] for k in cr.TILT]
    scene = {"ground_y": cl.GROUND_Y, "meshes": meshes, "axes": axes, "tcp0": (H @ np.r_[arm.tcp0, 1])[:3].tolist(),
             "panel_pivot": list(cl.SLEEVE), "box_B": (H @ box_rel).tolist(), "box_ground": cl.box_pose(cr.BOX_GROUND).tolist(),
             "bodies": [[cr.MASS[g], (H @ np.r_[arm.com[g], 1])[:3].round(1).tolist(), cr.NMOV[g]] for g in cr.MASS],
             "load_kg": cr.LOAD_KG, "caps": caps, "programs": progs, "fold": FOLD,
             "app0": (H[:3, :3] @ arm.app0).round(6).tolist()}
    tpl = open(os.path.join(ROOT, "tools", "cart_viewer.html"), encoding="utf-8").read()
    html = tpl.replace("/*SCENE_JSON*/null", json.dumps(scene, ensure_ascii=False, separators=(",", ":")))
    if a.offline:
        for rel in ("build/three.min.js", "examples/js/controls/OrbitControls.js"):
            tag = f'<script src="https://cdn.jsdelivr.net/npm/three@0.147.0/{rel}"></script>'
            code = open(os.path.join(a.offline, rel), encoding="utf-8").read().replace("</script", "<\\/script")
            html = html.replace(tag, "<script>\n" + code + "\n</script>")
    open(a.html, "w", encoding="utf-8").write(html)
    print(f"viewer -> {a.html} ({os.path.getsize(a.html) / 1e6:.1f} MB)")

if __name__ == "__main__":
    main()
