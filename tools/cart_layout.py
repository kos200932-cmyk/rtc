"""RTC-7 arm (user configuration J1..J7 + SZU gripper) on the wheeled cart (platform/CART, user models 2026-10-27).

Frame = the cart hull frame (platform/CART/CART.md): Y up, X along the cart (x = 0 front, robot at the rear), Z across
(+Z robot side, -Z the high side wall with the folding panel). Ground y = -597.5.

    python tools/cart_layout.py <out.png>      preview of the layout in the zero pose

Module use (reach studies): ARM parts in the arm frame (X = J1 up), CART parts in the hull frame, ROBOT = 4x4 arm -> hull.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CART_DIR = os.path.join(ROOT, "platform", "CART")
GROUND_Y = -597.5

def T(cols, t):
    """4x4 from the images of the file X, Y, Z axes (columns) and the translation."""
    M = np.eye(4); M[:3, :3] = np.array(cols, float).T; M[:3, 3] = t; return M

def Ry(deg):
    a = math.radians(deg); M = np.eye(4)
    M[0, 0] = math.cos(a); M[0, 2] = math.sin(a); M[2, 0] = -math.sin(a); M[2, 2] = math.cos(a); return M

# --- robot on the flange: base plate bottom (arm x = -12) on the flange top y = 550, J1 axis at (2359, 825).
# Arm X (J1) -> hull +Y; arm Z -> hull -X (the zero pose looks along the cart, to the front), then +15 deg about Y:
# the plate holes (15 + 30k deg in the arm frame) onto the flange holes (0 + 30k deg in the hull frame).
FLANGE_C = (2359.0, 825.0); FLANGE_TOP = 550.0; PLATE_T = 12.0
ROBOT = np.eye(4)
ROBOT[:3, :3] = Ry(15.0)[:3, :3] @ np.array([[0, 0, -1], [1, 0, 0], [0, -1, 0]], float)   # columns: arm X, Y, Z
ROBOT[:3, 3] = (FLANGE_C[0], FLANGE_TOP + PLATE_T, FLANGE_C[1])

AXLES_X = (-132.0, 1214.0, 2563.0); AXLE_Y = -336.5
SEATS = {"near": (1375.0, 523.0, 222.5), "far": (355.0, 523.0, 222.5)}    # top of the seat disc D358 (cone to y 583)
SLEEVE = (1764.0, 997.0, -897.5)                                            # panel pivot: top of the sleeve, axis Y

def cart_parts(panel_az=0.0, box_at=None):
    """[(name, step file, 4x4 file -> hull, colour)]; panel_az - turn of the panel about the sleeve axis, deg
    (+ = from +X towards -Z ... right-hand about +Y); box_at - (x, z) of the load centre on the ground or a seat name."""
    P = [("hull", "KORPUS.STEP", np.eye(4), "#9aa3a8")]
    for xa in AXLES_X:
        P.append(("wheel", "KOLESO.STEP", T([(0, 0, 1), (0, 1, 0), (-1, 0, 0)], (xa, AXLE_Y, 770)), "#4a4d50"))
        P.append(("wheel", "KOLESO.STEP", T([(0, 0, -1), (0, 1, 0), (1, 0, 0)], (xa, AXLE_Y, -770)), "#4a4d50"))
    Mp = T([(0, 0, -1), (0, 1, 0), (1, 0, 0)], (SLEEVE[0] + 435, SLEEVE[1] + 61, SLEEVE[2]))
    if panel_az:
        C = np.eye(4); C[:3, 3] = (SLEEVE[0], 0, SLEEVE[2]); Mp = C @ Ry(panel_az) @ np.linalg.inv(C) @ Mp
    P.append(("panel", "PANEL.STEP", Mp, "#3d6fae"))
    if box_at is not None:
        P.append(("box", "GRUZ-400.STEP", box_pose(box_at), "#c9a24a"))
    return P

def box_pose(at):
    """Load "Груз 400" pin up: on a seat (its D128 recess on the seat boss) or on the ground at (x, z)."""
    if isinstance(at, str):
        x, y, z = SEATS[at]
    else:
        x, z = at; y = GROUND_Y
    # file: cube x +-200, y -200..200, z 0..400, pin D60 on the -Y face, recess D128 on the +Y face
    return T([(1, 0, 0), (0, -1, 0), (0, 0, -1)], (x, y + 200, z + 200))

def box_top(at):
    """Top face of the cube (pin root) - the TCP when the load is gripped (user 2026-10-27)."""
    M = box_pose(at); return (M @ np.r_[0.0, -200.0, 200.0, 1.0])[:3]      # file: centre (0,0,200), pin face y=-200

# ---------------------------------------------------------------- geometry
def arm_parts():
    """[(name, OCC shape in the arm frame, group)] of the full arm + SZU (zero pose), as tools/sweep_user_full.py."""
    argv = sys.argv; sys.argv = [argv[0]]
    try:
        import sweep_user_full as sw
    finally:
        sys.argv = argv
    import link_build as lb, gen_user_full as gf
    pts = [(float(l.split()[1]), float(l.split()[2])) for l in open(os.path.join(ROOT, "links-user/SZU/SZU.txt"),
           encoding="utf-8") if l.startswith("P ")]
    szu = sw.mv(lb.revolved(np.zeros(3), [1, 0, 0], pts), gf.szu_frame())
    return list(sw.P) + [("SZU", szu, "F")], gf.szu_frame()

def load_step(path):
    from OCP.STEPControl import STEPControl_Reader
    r = STEPControl_Reader(); r.ReadFile(path); r.TransferRoots(); return r.OneShape()

def mesh(shape, M=np.eye(4), defl=1.0):
    import pyvista as pv, link_build as lb
    tri = np.array(lb.triangles(shape, defl)); pts = tri.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    return pv.PolyData(pts, np.hstack([np.full((len(tri), 1), 3), np.arange(len(pts)).reshape(-1, 3)]).ravel()).clean()

ARM_COL = {"B": "#c8a0c8", "J1": "#b8c2cc", "L1": "#d49a90", "J2": "#5f6a74", "L2": "#c9bfae", "J3": "#b8c2cc",
           "L3": "#e0b93c", "J4": "#b8c2cc", "L4": "#e0b93c", "J5": "#b8c2cc", "L5": "#e0b93c", "J6": "#b8c2cc",
           "L6": "#e0b93c", "J7": "#b8c2cc", "F": "#2a5d9f"}

def preview(png):
    import pyvista as pv
    pv.global_theme.allow_empty_mesh = True
    arm, F = arm_parts()
    box_ground = (2659.0 + 100.0 + 200.0, 0.0)       # scenario 1: the load on the ground, 100 mm behind the rear end
    Ms = [(mesh(s, ROBOT), ARM_COL.get(g, "#b8c2cc"), 1.0) for n, s, g in arm]
    cache = {}
    for n, f, M, c in cart_parts(box_at=box_ground):
        if f not in cache: cache[f] = load_step(os.path.join(CART_DIR, f))
        Ms.append((mesh(cache[f], M, 2.0), c, 1.0))
    if "GRUZ-400.STEP" in cache:                      # scenario 2 target: ghost of the load on the far seat
        Ms.append((mesh(cache["GRUZ-400.STEP"], box_pose("far"), 2.0), "#c9a24a", 0.35))
    tcp = (ROBOT @ np.r_[F[:3, 3] + F[:3, 0] * 150.0, 1])[:3]
    g = pv.Plane(center=(1300, GROUND_Y, 0), direction=(0, 1, 0), i_size=6000, j_size=5000)
    pl = pv.Plotter(off_screen=True, window_size=(2600, 1300), shape=(1, 2))
    views = [((1.0, 0.55, 1.1), "RTC-7 + SZU on the cart, zero pose (robot side)"),
             ((-0.9, 0.6, -1.0), "panel side; ghost load = far seat (target), solid load = on the ground")]
    for i, (cam, title) in enumerate(views):
        pl.subplot(0, i); pl.set_background("white")
        pl.add_mesh(g, color="#d8cdb8", opacity=0.6)
        for m, c, op in Ms: pl.add_mesh(m, color=c, opacity=op, specular=0.2)
        pl.add_mesh(pv.Sphere(radius=25, center=tcp), color="red")
        pl.add_mesh(pv.Line((FLANGE_C[0], FLANGE_TOP, FLANGE_C[1]), (FLANGE_C[0], 3300, FLANGE_C[1])), color="red", line_width=2)
        pl.view_vector(cam, viewup=(0, 1, 0)); pl.reset_camera(); pl.camera.zoom(1.25)
        pl.add_text(title, font_size=11, color="black")
    pl.screenshot(png); print("TCP (zero pose) hull", tcp.round(1), "->", png)

if __name__ == "__main__":
    preview(sys.argv[1] if len(sys.argv) > 1 else "cart_layout.png")
