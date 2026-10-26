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

def build_program(name, wps, arm, chk, box_rel, dt=0.25):
    """wps: [(q, az, box_state, label)] - segment i goes from wps[i] to wps[i+1] with the state / label of wps[i+1]."""
    segs = []; q_prev = np.asarray(wps[0][0], float)
    box_at = {}
    for (qa, aza, _, _), (qb, azb, st, lab) in zip(wps[:-1], wps[1:]):
        q0 = q_prev; q1 = unwrap(q0, qb); q_prev = q1
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
        q = np.array(s["q0"]) + w * (np.array(s["q1"]) - np.array(s["q0"])); az = s["az0"] + w * (s["az1"] - s["az0"])
        tcp = arm.tcp(q)[0]
        seat_contact = s["box"] == "held" and tcp[1] < 923 + 12 and s["label"].startswith("установка")
        h = chk.hits(q, s["box"], box_rel, az, box_at.get(s["box"][3:]) if s["box"].startswith("at:") else None, seat_contact)
        txt = ", ".join(sorted({f"{NAMES.get(a, a)} / {NAMES.get(b, b)}" for a, b in h}))
        checks.append(txt); n_bad += bool(txt)
    print(f"{name}: {len(segs)} segments, {total:.1f} s, samples with contacts: {n_bad}/{len(checks)}",
          sorted({c for c in checks if c})[:6])
    return {"name": name, "segs": segs, "dt": dt, "checks": checks,
            "box_at": {k: M.tolist() for k, M in box_at.items()}}

def lift_place(arm, R, seat, chk, box_rel):
    q1, q2, q3 = [np.array(v) for v in R["q_lift"]]
    qa, qb, q4, q5 = [np.array(v) for v in R["q_" + seat]]
    st = cl.box_top(seat)
    q6 = arm.ik(st + np.array([0, 150, 0]), cr.DOWN, q5)[0]
    z = np.zeros(7); s_ = "ближним" if seat == "near" else "дальним"
    W = [(z, 0, "ground", "исходная поза"),
         (q1, 0, "ground", "подход: СЗУ над штырём груза (+150 мм)"),
         (q2, 0, "ground", "надевание СЗУ на штырь до касания грани куба"),
         (q2, 0, "held", "фиксация груза"),
         (q3, 0, "held", "подъём на 500 мм"),
         (qa, 0, "held", "подъём на высоту переноса (TCP 1500)"),
         (qb, 0, "held", f"перенос: над {s_} посадочным местом"),
         (q4, 0, "held", "опускание: груз в 150 мм над конусом"),
         (q5, 0, "held", "установка на посадочное место"),
         (q5, 0, "at:" + seat, "освобождение груза"),
         (q6, 0, "at:" + seat, "отвод СЗУ вверх"),
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
             "load_kg": cr.LOAD_KG, "caps": caps, "programs": progs}
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
