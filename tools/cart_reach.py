"""Reach of the RTC-7 arm (+ SZU gripper) on the wheeled cart: kinematics, IK, collisions (FCL meshes), gravity torques.

Frames: tools/cart_layout.py (hull frame, Y up, ground y = -597.5). Joint axes: tools/sweep_user_full.py (arm frame, zero
pose), J7 = the SZU axis. Product of exponentials: group g is moved by the joints before it (ORDER / NMOV).
TCP = SZU end face (card x = 150), approach = SZU +X.

    python tools/cart_reach.py scen       scenarios 1-2 (lift from the ground, place on the far / near seat)
    python tools/cart_reach.py panel      scenario 3 (panel coverage vs panel turn)
"""
import sys, os, math, json, time
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cart_layout as cl

ORDER = ["B", "J1", "L1", "J2", "L2", "J3", "L3", "J4", "L4", "J5", "L5", "J6", "L6", "J7", "F"]
NMOV = {"B": 0, "J1": 0, "L1": 1, "J2": 1, "L2": 2, "J3": 2, "L3": 3, "J4": 3, "L4": 4, "J5": 4, "L5": 5, "J6": 5,
        "L6": 6, "J7": 6, "F": 7}
# masses, kg (STATUS_2026-10-26.md; joints - load model estimates; SZU steel assumed)
MASS = {"L1": 1.39 + 5.73, "J2": 25.1, "L2": 7.25, "J3": 20.0, "L3": 13.0, "J4": 15.0, "L4": 6.84, "J5": 6.0,
        "L5": 5.70, "J6": 3.5, "L6": 1.41, "J7": 1.8, "F": 4.05}
LOAD_KG = 8.0
# allowed torque about the axis = min(reducer rated, motor rated x ratio x 0.8), N·m (robot/RTC-7-loads-v2.md)
CAP = {1: (62, 0.94 * 79 * 0.8), 2: (1400, 9.0 * 153 * 0.8), 3: (415, 5.5 * 99 * 0.8), 4: (375, 5.5 * 79 * 0.8),
       5: (103, 0.94 * 79 * 0.8), 6: (62, 0.94 * 49 * 0.8)}
TILT = {3: 1032, 5: 336}          # allowed tilting moment of KB50 (J3) and KB32 (J5), N·m
G = 9.81

def rot(o, d, ang):
    d = np.asarray(d, float) / np.linalg.norm(d); a = ang
    K = np.array([[0, -d[2], d[1]], [d[2], 0, -d[0]], [-d[1], d[0], 0]])
    R = np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = o - R @ o; return M

class Arm:
    def __init__(self, geometry=True):
        argv = sys.argv; sys.argv = [argv[0]]
        try:
            import sweep_user_full as sw
        finally:
            sys.argv = argv
        import gen_user_full as gf
        self.F = gf.szu_frame()
        self.axes = [sw.axis(f"J{k}") for k in range(1, 7)] + [(self.F[:3, 3].copy(), self.F[:3, 0].copy())]
        self.tcp0 = self.F[:3, 3] + 150.0 * self.F[:3, 0]
        self.app0 = self.F[:3, 0].copy()
        self.groups = {}
        if geometry:
            import link_build as lb
            parts, _ = cl.arm_parts()
            com = {}
            for n, s, g in parts:
                tri = np.array(lb.triangles(s, 1.5))
                self.groups.setdefault(g, []).append(tri)
                v, c = lb.volume(s)
                if v > 0:
                    a = com.setdefault(g, [0.0, np.zeros(3)]); a[0] += v; a[1] += v * np.array([c.X(), c.Y(), c.Z()])
            self.groups = {g: np.concatenate(t) for g, t in self.groups.items()}
            self.com = {g: a[1] / a[0] for g, a in com.items()}

    def fk(self, q):
        """q, rad (7) -> {group: 4x4 in the arm frame}, list of cumulative joint transforms."""
        cum = [np.eye(4)]
        for (o, d), qi in zip(self.axes, q):
            cum.append(cum[-1] @ rot(o, d, qi))
        return {g: cum[n] for g, n in NMOV.items()}, cum

    def tcp(self, q):
        _, cum = self.fk(q); M = cl.ROBOT @ cum[7]
        return (M @ np.r_[self.tcp0, 1])[:3], M[:3, :3] @ self.app0, M

    def ik(self, p, a, seed, fix=(), w_a=800.0, reg=0.02):
        """TCP at p (hull), approach a (hull unit); q3/q5 may be fixed (indices in fix keep the seed value)."""
        from scipy.optimize import least_squares
        seed = np.asarray(seed, float); free = [i for i in range(7) if i not in fix]
        def res(x):
            q = seed.copy(); q[free] = x
            pt, at, _ = self.tcp(q)
            return np.r_[pt - p, w_a * (at - a), reg * 100 * (x - seed[free])]
        r = least_squares(res, seed[free], xtol=1e-10, ftol=1e-10, max_nfev=400)
        q = seed.copy(); q[free] = r.x
        pt, at, _ = self.tcp(q)
        q = (q + math.pi) % (2 * math.pi) - math.pi
        return q, float(np.linalg.norm(pt - p)), float(math.degrees(math.acos(np.clip(at @ a, -1, 1))))

    def torques(self, q, load_com=None):
        """Gravity torque about each joint axis J1..J6 (N·m) and the tilting moment at J3 / J5 (N·m); gravity -Y hull."""
        Tg, cum = self.fk(q)
        g_arm = cl.ROBOT[:3, :3].T @ np.array([0, -G, 0])        # gravity in the arm frame
        bodies = [(MASS[g], (Tg[g] @ np.r_[self.com[g], 1])[:3], NMOV[g]) for g in MASS]
        if load_com is not None:                                  # load COM given in the hull frame
            bodies.append((LOAD_KG, (np.linalg.inv(cl.ROBOT) @ np.r_[load_com, 1])[:3], 7))
        tq, tilt = {}, {}
        for k in range(1, 7):
            o, d = self.axes[k - 1]; M = cum[k - 1]; o = (M @ np.r_[o, 1])[:3]; d = M[:3, :3] @ d
            m = np.zeros(3)
            for mass, c, n in bodies:
                if n >= k: m += np.cross(c - o, mass * g_arm)
            tq[k] = float(m @ d) / 1000.0; tilt[k] = float(np.linalg.norm(m - (m @ d) * d)) / 1000.0   # N·mm -> N·m
        return tq, tilt

def fcl_obj(tri, M=np.eye(4)):
    import fcl
    v = tri.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    m = fcl.BVHModel(); m.beginModel(len(v), len(tri))
    m.addSubModel(v, np.arange(len(v)).reshape(-1, 3)); m.endModel()
    return fcl.CollisionObject(m)

def fcl_local(tri):
    import fcl
    v = tri.reshape(-1, 3); m = fcl.BVHModel(); m.beginModel(len(v), len(tri))
    m.addSubModel(v, np.arange(len(v)).reshape(-1, 3)); m.endModel(); return m

def set_tf(obj, M):
    import fcl
    obj.setTransform(fcl.Transform(M[:3, :3], M[:3, 3]))

class Scene:
    """Arm group meshes (moving) + cart meshes (static, hull frame); collisions and clearances."""
    def __init__(self, arm, panel_az=0.0, box_at=None):
        import fcl, link_build as lb
        self.arm = arm
        self.arm_obj = {g: fcl.CollisionObject(fcl_local(t)) for g, t in arm.groups.items()}
        self.cart_tri = {}
        cache = {}
        for n, f, M, c in cl.cart_parts(panel_az=panel_az, box_at=box_at):
            if f not in cache: cache[f] = np.array(lb.triangles(cl.load_step(os.path.join(cl.CART_DIR, f)), 2.0))
            t = cache[f] @ M[:3, :3].T + M[:3, 3]
            self.cart_tri.setdefault(n, []).append(t)
        self.cart_tri = {n: np.concatenate(t) for n, t in self.cart_tri.items()}
        self.box_local = cache.get("GRUZ-400.STEP")
        if self.box_local is None:
            self.box_local = np.array(lb.triangles(cl.load_step(os.path.join(cl.CART_DIR, "GRUZ-400.STEP")), 2.0))
        self.cart_obj = {n: fcl_obj(t) for n, t in self.cart_tri.items()}
        self.box_obj = fcl.CollisionObject(fcl_local(self.box_local))
        # pairs in contact by design in the zero pose (base plate on the flange, joint on its links ...)
        self.allowed = set()
        for a, b in self.pairs(np.zeros(7), None, contact=True): self.allowed.add((a, b))

    def set_panel(self, az):
        import link_build as lb
        for n, f, M, c in cl.cart_parts(panel_az=az):
            if n == "panel":
                if not hasattr(self, "_panel_local"):
                    self._panel_local = np.array(lb.triangles(cl.load_step(os.path.join(cl.CART_DIR, f)), 2.0))
                self.cart_obj["panel"] = fcl_obj(self._panel_local, M); self.cart_tri["panel"] = None
                self.panel_M = M

    def place(self, q, box_rel=None):
        Tg, cum = self.arm.fk(q)
        for g, o in self.arm_obj.items(): set_tf(o, cl.ROBOT @ Tg[g])
        if box_rel is not None: set_tf(self.box_obj, cl.ROBOT @ cum[7] @ box_rel)
        return Tg, cum

    def pairs(self, q, box_rel, contact=False, skip=()):
        """colliding pairs (name, name) for pose q; box_rel - the load attached to the SZU (4x4 in the TCP frame)."""
        import fcl
        self.place(q, box_rel)
        req = fcl.CollisionRequest(); hits = []
        objs = dict(self.arm_obj)
        if box_rel is not None: objs["LOAD"] = self.box_obj
        names = list(objs)
        for a in names:                                            # arm / load vs cart
            for b, ob in self.cart_obj.items():
                if (a, b) in skip or (a, b) in getattr(self, "allowed", ()): continue
                if a == "LOAD" and b == "box": continue
                r = fcl.CollisionResult()
                if fcl.collide(objs[a], ob, req, r): hits.append((a, b))
        for i, a in enumerate(names):                              # self collisions
            for b in names[i + 1:]:
                if (a, b) in getattr(self, "allowed", ()) or {a, b} == {"F", "LOAD"}: continue
                ia = ORDER.index(a) if a in ORDER else 99; ib = ORDER.index(b) if b in ORDER else 99
                if abs(ia - ib) <= 1: continue
                r = fcl.CollisionResult()
                if fcl.collide(objs[a], objs[b], req, r): hits.append((a, b))
        return hits

    def clearance(self, q, box_rel, skip=()):
        """min distance arm (+load) - cart objects and to the ground, mm: [(dist, a, b)] sorted."""
        import fcl
        self.place(q, box_rel); out = []
        objs = dict(self.arm_obj)
        if box_rel is not None: objs["LOAD"] = self.box_obj
        for a, oa in objs.items():
            if a in ("B", "J1"): continue
            for b, ob in self.cart_obj.items():
                if (a, b) in skip or (a == "LOAD" and b == "box"): continue
                r = fcl.DistanceResult(); d = fcl.distance(oa, ob, fcl.DistanceRequest(), r); out.append((d, a, b))
        Tg, cum = self.arm.fk(q); low = 1e9
        for g, t in self.arm.groups.items():
            if g in ("B", "J1"): continue
            M = cl.ROBOT @ Tg[g]; low = min(low, (t.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])[:, 1].min())
        if box_rel is not None:
            M = cl.ROBOT @ cum[7] @ box_rel; low_b = (self.box_local.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])[:, 1].min()
            out.append((low_b - cl.GROUND_Y, "LOAD", "ground"))
        out.append((low - cl.GROUND_Y, "arm", "ground"))
        return sorted(out)

# ---------------------------------------------------------------- scenarios 1-2
DOWN = np.array([0.0, -1.0, 0.0])
TRANSIT = 1500.0                  # TCP height of the transfer, hull y (load bottom at 1100)
BOX_GROUND = (2959.0, 0.0)        # load on the ground, 100 mm behind the rear end, on the cart axis (user 2026-10-27)

def solve(arm, p, a, seeds, prefer=None, scene=None, box_rel=None, skip=(), n_ok=1):
    """IK from several seeds -> [(q, err, ang, hits)] sorted: collision-free first, then closest to prefer."""
    sols = []
    for s in seeds:
        q, e, an = arm.ik(p, a, s)
        if e > 0.5 or an > 0.2: continue
        if any(np.allclose(q, x[0], atol=1e-3) for x in sols): continue
        hits = scene.pairs(q, box_rel, skip=skip) if scene is not None else []
        sols.append((q, e, an, hits))
    key = lambda x: (len(x[3]) > 0, 0 if prefer is None else float(np.abs(((x[0] - prefer + math.pi) % (2 * math.pi)) - math.pi).sum()))
    return sorted(sols, key=key)

def seeds_around(q0, n=40, rng=None, spread=1.2):
    rng = rng or np.random.default_rng(7)
    S = [np.asarray(q0, float)]
    for _ in range(n):
        s = np.asarray(q0, float) + rng.normal(0, spread, 7); s[2] *= 0.3; s[4] *= 0.3; S.append(s)
    return S

def ratio(arm, q, load_com):
    tq, tilt = arm.torques(q, load_com)
    r = {f"J{k}": abs(tq[k]) / min(CAP[k]) for k in CAP}
    r.update({f"J{k}tilt": tilt[k] / TILT[k] for k in TILT})
    return tq, tilt, r

def segment(scene, qa, qb, box_rel, n=24, skip=()):
    bad = []
    for t in np.linspace(0, 1, n + 1)[1:-1]:
        h = scene.pairs(qa + t * (((qb - qa + math.pi) % (2 * math.pi)) - math.pi), box_rel, skip=skip)
        if h: bad.append((round(float(t), 2), h))
    return bad

def scen(out_json):
    arm = Arm()
    scA = Scene(arm, box_at=BOX_GROUND)            # load on the ground
    scB = Scene(arm, box_at=None); scB.allowed = scA.allowed
    top = cl.box_top(BOX_GROUND)
    R = {}
    # elbow-up seeds: shoulder forward, elbow bent back
    base = [math.atan2(*(np.array([top[0], top[2]]) - np.array(cl.FLANGE_C))[::-1]) for _ in range(1)]
    rng = np.random.default_rng(3)
    seeds = [rng.uniform(-math.pi, math.pi, 7) * np.array([1, 0.8, 0.3, 1, 0.3, 1, 1]) for _ in range(120)]
    def report(name, q, box_rel, load_com, scene, skip=()):
        tq, tilt, r = ratio(arm, q, load_com)
        cl_ = scene.clearance(q, box_rel, skip=skip)
        R[name] = {"q_deg": [round(math.degrees(v), 1) for v in q], "tcp": arm.tcp(q)[0].round(1).tolist(),
                   "hits": scene.pairs(q, box_rel, skip=skip),
                   "clearance": [(round(d, 1), a, b) for d, a, b in cl_[:6]],
                   "torque_Nm": {k: round(v, 1) for k, v in tq.items()}, "tilt_Nm": {k: round(tilt[k], 1) for k in TILT},
                   "load_ratio": {k: round(v, 2) for k, v in r.items()}}
        print(name, R[name]["q_deg"], "hits", R[name]["hits"], "clear", R[name]["clearance"][:3],
              "ratio", {k: v for k, v in R[name]["load_ratio"].items() if v > 0.5}, flush=True)
    # P1 pre-grasp, P2 grasp (SZU face on the cube top)
    s1 = solve(arm, top + np.array([0, 150, 0]), DOWN, seeds, scene=scA)
    print("P1 solutions:", len(s1), "collision-free:", sum(1 for x in s1 if not x[3]))
    q1 = s1[0][0]
    q2 = solve(arm, top, DOWN, seeds_around(q1, 10, spread=0.05), prefer=q1, scene=scA, skip={("F", "box")})[0][0]
    box_rel = np.linalg.inv(cl.ROBOT @ arm.fk(q2)[1][7]) @ cl.box_pose(BOX_GROUND)
    com_of = lambda q: (cl.ROBOT @ arm.fk(q)[1][7] @ box_rel @ np.r_[0, 0, 200, 1])[:3]
    report("P1_pregrasp", q1, None, None, scA)
    report("P2_grasp", q2, None, None, scA, skip={("F", "box")})
    R["P2_grasp"]["torque_with_load"] = {k: round(v, 1) for k, v in arm.torques(q2, com_of(q2))[0].items()}
    q3 = solve(arm, top + np.array([0, 500, 0]), DOWN, seeds_around(q2, 10, spread=0.05), prefer=q2, scene=scB, box_rel=box_rel)[0][0]
    report("P3_lift", q3, box_rel, com_of(q3), scB)
    R["seg_P1_P2"] = segment(scA, q1, q2, None, skip={("F", "box")})
    R["seg_P2_P3"] = segment(scB, q2, q3, box_rel)
    for seat in ("far", "near"):
        st = cl.box_top(seat)                                   # cube top when seated = TCP at placing
        cand = solve(arm, st + np.array([0, 150, 0]), DOWN, [q3] + seeds_around(q3, 60, spread=1.0) + seeds,
                     prefer=q3, scene=scB, box_rel=box_rel)
        if not cand: print(seat, "no IK"); R[seat] = "no IK"; continue
        q4 = cand[0][0]
        # transit at TCP y = TRANSIT (load bottom above the side wall / cup y 997 with margin): up above the
        # pick point, over to above the seat, then down
        qa = solve(arm, np.array([top[0], TRANSIT, top[2]]), DOWN, seeds_around(q3, 20, spread=0.3), prefer=q3,
                   scene=scB, box_rel=box_rel)[0][0]
        qb = solve(arm, np.array([st[0], TRANSIT, st[2]]), DOWN, [q4] + seeds_around(q4, 20, spread=0.3), prefer=q4,
                   scene=scB, box_rel=box_rel)[0][0]
        report(f"P3h_up_{seat}", qa, box_rel, com_of(qa), scB)
        report(f"P4h_over_{seat}", qb, box_rel, com_of(qb), scB)
        report(f"P4_above_{seat}", q4, box_rel, com_of(q4), scB)
        c5 = solve(arm, st + np.array([0, 2, 0]), DOWN, seeds_around(q4, 10, spread=0.05), prefer=q4, scene=scB, box_rel=box_rel)
        q5 = c5[0][0]
        report(f"P5_place_{seat}", q5, box_rel, com_of(q5), scB)
        R[f"seg_P3_P3h_{seat}"] = segment(scB, q3, qa, box_rel)
        R[f"seg_P3h_P4h_{seat}"] = segment(scB, qa, qb, box_rel, n=48)
        R[f"seg_P4h_P4_{seat}"] = segment(scB, qb, q4, box_rel)
        R[f"seg_P4_P5_{seat}"] = segment(scB, q4, q5, box_rel)
        R[f"q_{seat}"] = [qa.tolist(), qb.tolist(), q4.tolist(), q5.tolist()]
    R["q_lift"] = [q1.tolist(), q2.tolist(), q3.tolist()]; R["box_rel"] = box_rel.tolist()
    json.dump(R, open(out_json, "w"), ensure_ascii=False, indent=1, default=str)
    for k in R:
        if k.startswith("seg"): print(k, "collisions on the way:", R[k][:3] if R[k] else "none")
    return R

# ---------------------------------------------------------------- pictures
def pv_mesh(tri, M):
    import pyvista as pv
    v = tri.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    return pv.PolyData(v, np.hstack([np.full((len(tri), 1), 3), np.arange(len(v)).reshape(-1, 3)]).ravel())

def poses_png(arm, scene, frames, png, cols=3, cam=(1.0, 0.75, 1.15), size=(900, 760)):
    """frames: [(title, q, box_rel or None (load on the ground / seat per scene), extra [(tri, M, colour, opacity)])]"""
    import pyvista as pv
    pv.global_theme.allow_empty_mesh = True
    rows = (len(frames) + cols - 1) // cols
    pl = pv.Plotter(off_screen=True, window_size=(size[0] * cols, size[1] * rows), shape=(rows, cols))
    COL = {"hull": "#9aa3a8", "wheel": "#4a4d50", "panel": "#3d6fae", "box": "#c9a24a"}
    ground = pv.Plane(center=(1300, cl.GROUND_Y, 0), direction=(0, 1, 0), i_size=6000, j_size=5000)
    base_scene = scene
    for i, fr in enumerate(frames):
        title, q, box_rel, extra = fr[:4]; scene = fr[4] if len(fr) > 4 else base_scene
        pl.subplot(i // cols, i % cols); pl.set_background("white")
        pl.add_mesh(ground, color="#d8cdb8", opacity=0.6)
        for n, t in scene.cart_tri.items():
            if t is None: continue
            if n == "box" and box_rel is not None: continue
            pl.add_mesh(pv_mesh(t, np.eye(4)), color=COL.get(n, "#999"))
        if getattr(scene, "panel_M", None) is not None and scene.cart_tri.get("panel") is None:
            pl.add_mesh(pv_mesh(scene._panel_local, scene.panel_M), color=COL["panel"])
        Tg, cum = arm.fk(q)
        for g, t in arm.groups.items():
            pl.add_mesh(pv_mesh(t, cl.ROBOT @ Tg[g]), color=cl.ARM_COL.get(g, "#b8c2cc"), specular=0.2)
        if box_rel is not None:
            pl.add_mesh(pv_mesh(scene.box_local, cl.ROBOT @ cum[7] @ box_rel), color=COL["box"])
        for t, M, c, op in extra or []:
            pl.add_mesh(pv_mesh(t, M), color=c, opacity=op)
        pl.add_mesh(pv.Sphere(radius=22, center=arm.tcp(q)[0]), color="red")
        pl.view_vector(cam, viewup=(0, 1, 0)); pl.reset_camera(); pl.camera.zoom(1.3)
        pl.add_text(title, font_size=10, color="black")
    pl.screenshot(png)

def scen_png(json_path, png):
    R = json.load(open(json_path, encoding="utf-8"))
    arm = Arm(); scA = Scene(arm, box_at=BOX_GROUND); scB = Scene(arm, box_at=None)
    br = np.array(R["box_rel"]); q1, q2, q3 = [np.array(v) for v in R["q_lift"]]
    qa, qb, q4, q5 = [np.array(v) for v in R["q_far"]]
    na, nb, n4, n5 = [np.array(v) for v in R["q_near"]]
    fr = [("1. grasp: SZU face on the cube top", q2, None, None),
          ("1. lift + 500 mm", q3, br, None),
          ("transfer height: TCP y = 1500", qa, br, None),
          ("2. over the far seat (x = 355)", qb, br, None),
          ("2. placed on the far seat", q5, br, None),
          ("2'. placed on the near seat (x = 1375)", n5, br, None)]
    fr[0] = fr[0] + (scA,)
    poses_png(arm, scB, fr, png, cols=3)

# ---------------------------------------------------------------- scenario 3: the panel
# front (solar) face of the panel sheet in the PANEL.STEP frame: plane through (177, 59) along s = (0.277, 0.961, 0)
# and z, outward normal (-0.961, 0.277, 0); sheet length 1640, width z -1330..460 (inset 40 mm for the grid)
P_B0 = np.array([177.0, 59.0, 0.0]); P_S = np.array([0.277, 0.961, 0.0]); P_S /= np.linalg.norm(P_S)
P_N = np.array([-0.961, 0.277, 0.0]); P_N /= np.linalg.norm(P_N)
def panel_grid(nu=7, nw=9):
    U = np.linspace(40, 1600, nu); W = np.linspace(-1290, 420, nw)
    return [(i, j, P_B0 + u * P_S + np.array([0, 0, w])) for i, u in enumerate(U) for j, w in enumerate(W)]

def panel(out_json, az_list=None, nseed=14):
    arm = Arm(); sc = Scene(arm, box_at=None)
    az_list = az_list if az_list is not None else list(range(-180, 180, 15))
    grid = panel_grid(); rng = np.random.default_rng(11)
    seeds0 = [rng.uniform(-math.pi, math.pi, 7) * np.array([1, 0.8, 0.3, 1, 0.3, 1, 1]) for _ in range(nseed)]
    out = {"grid": [(i, j) for i, j, _ in grid], "az": {}}
    t0 = time.time()
    for az in az_list:
        sc.set_panel(az); M = sc.panel_M
        n_out = M[:3, :3] @ P_N
        res = {}; prev = []
        home_hits = sc.pairs(np.zeros(7), None)
        for i, j, p in grid:
            ph = (M @ np.r_[p, 1])[:3] + 5.0 * n_out               # TCP 5 mm in front of the face
            near = [q for (ii, jj), q in prev if abs(ii - i) + abs(jj - j) <= 2]
            best = None
            for s in near[-3:] + seeds0:
                q, e, an = arm.ik(ph, -n_out, s)
                if e > 1.0 or an > 0.5: continue
                h = sc.pairs(q, None)
                if not h: best = (q, []); break
                if best is None: best = (q, h)
            if best is None: res[f"{i},{j}"] = "far"
            elif best[1]: res[f"{i},{j}"] = "hit:" + "+".join(sorted({f"{a}/{b}" for a, b in best[1]}))
            else: res[f"{i},{j}"] = "ok"; prev.append(((i, j), best[0])); out.setdefault("q", {})[f"{az}:{i},{j}"] = best[0].tolist()
        ok = sum(v == "ok" for v in res.values())
        out["az"][str(az)] = {"res": res, "ok": ok, "home_hits": home_hits}
        print(f"az {az:4d}: ok {ok}/{len(grid)}  far {sum(v=='far' for v in res.values())}  hit {sum(v.startswith('hit') for v in res.values())}"
              f"  home {home_hits}  {time.time()-t0:.0f}s", flush=True)
        json.dump(out, open(out_json, "w"), indent=0)
    return out

def panel_png(json_path, png, show_az=None):
    """Coverage of the panel face (front, as seen from the deck side) for several panel turns + the union."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    D = json.load(open(json_path)); A = D["az"]; azs = sorted(A, key=float)
    nu = 1 + max(i for i, j in D["grid"]); nw = 1 + max(j for i, j in D["grid"])
    def grid(az):
        g = np.zeros((nu, nw))
        for k, v in A[az]["res"].items():
            i, j = map(int, k.split(",")); g[i, j] = 2 if v == "ok" else (1 if v.startswith("hit") else 0)
        return g
    best = sorted(azs, key=lambda a: -A[a]["ok"])
    show = show_az or best[:5]
    union = np.zeros((nu, nw)); cnt = np.zeros((nu, nw))
    for a in azs:
        g = grid(a); union = np.maximum(union, g); cnt += (g == 2)
    cm = ListedColormap(["#d9534f", "#f0ad4e", "#5cb85c"])
    fig, ax = plt.subplots(1, len(show) + 2, figsize=(3.1 * (len(show) + 2), 4.6))
    ext = (-1290 - 107, 420 + 107, 40 - 130, 1600 + 130)
    for k, a in enumerate(show):
        ax[k].imshow(grid(a), origin="lower", cmap=cm, vmin=0, vmax=2, extent=ext, aspect="auto")
        ax[k].set_title(f"turn {float(a):+.0f}°: {A[a]['ok']}/{nu*nw}")
    ax[-2].imshow(union, origin="lower", cmap=cm, vmin=0, vmax=2, extent=ext, aspect="auto")
    ax[-2].set_title(f"union of all turns: {int((union==2).sum())}/{nu*nw}")
    im = ax[-1].imshow(cnt, origin="lower", cmap="viridis", extent=ext, aspect="auto")
    ax[-1].set_title("number of turns reaching"); fig.colorbar(im, ax=ax[-1], fraction=0.05)
    for a_ in ax:
        a_.set_xlabel("across the panel z, mm"); a_.set_ylabel("up the sheet, mm")
    fig.suptitle("Panel front face: green - reached (no contacts), orange - reached with a contact, red - out of reach")
    plt.tight_layout(); plt.savefig(png, dpi=90)
    return best

if __name__ == "__main__":
    if sys.argv[1:2] == ["scen"]: scen(sys.argv[2] if len(sys.argv) > 2 else "platform/CART/reach_scen.json")
    if sys.argv[1:2] == ["panel"]: panel(sys.argv[2] if len(sys.argv) > 2 else "platform/CART/reach_panel.json")
