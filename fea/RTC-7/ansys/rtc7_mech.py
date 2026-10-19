# RTC-7 link strength - Mechanical script (Ansys Mechanical 2024 R1, IronPython 2.7 / CPython).
# GENERATED for the data in rtc7_fea.json (tools/fea_export.py). ASCII only on purpose.
#
# Run automatically by rtc7_wb.py (Workbench), or by hand in Mechanical:
#   Automation > Scripting > open this file, set CONFIG (and MODEL_ID, or leave None = found by the geometry), Run.
#
# What it does in the open Static Structural analysis:
#   * finds the FIXED and LOAD interface faces by the geometric rules of rtc7_fea.json (the same rules were
#     checked on the STEP when the data was made; the face areas are compared with the expected ones);
#   * named selections NS_FIXED / NS_LOAD, material AMg6 on the body, mesh size;
#   * Fixed Support on NS_FIXED; Remote Point (Rigid) at the LOAD interface centre; Remote Force + Moment on it
#     and an Acceleration (gravity + own acceleration of the part) - one load step per load case;
#   * results per case: equivalent stress, total deformation, force / moment reaction of the support;
#   * solves (SOLVE = True) and writes results_<MODEL>.csv next to rtc7_fea.json: max stress, allowable,
#     safety factor, reaction found vs expected (the check that the loads went in right).
import json
import math
import os

try:
    CONFIG
except NameError:
    CONFIG = r"C:\rtc\fea\RTC-7\rtc7_fea.json"        # <- path to rtc7_fea.json when run by hand
try:
    MODEL_ID
except NameError:
    MODEL_ID = None                                    # None: the model is recognised by its geometry
try:
    SOLVE
except NameError:
    SOLVE = True

LOGLINES = []


def log(msg):
    LOGLINES.append(msg)
    try:
        ExtAPI.Log.WriteMessage(msg)
    except Exception:
        pass
    print(msg)


def q(value, unit):
    return Quantity(value, unit)


def tunit(alts):
    """first unit string Mechanical accepts"""
    for u in alts:
        try:
            Quantity(1.0, u)
            return u
        except Exception:
            pass
    return alts[0]


U_TIME = tunit(["sec", "s"])
U_ACC = tunit(["mm sec^-1 sec^-1", "mm s^-1 s^-1", "mm s^-2"])
U_MOM = tunit(["N mm", "N*mm"])

cfg = json.load(open(CONFIG))
TOL = float(cfg.get("tolerance_mm", 0.05))
AX = {"X": 0, "Y": 1, "Z": 2}

ExtAPI.Application.ActiveUnitSystem = MechanicalUnitSystem.StandardNMM

# ---------------------------------------------------------------- geometry: faces with their vertices
faces = []          # (id, [ (x,y,z) ...], area)


def face_vertices(f):
    try:
        return [(v.X, v.Y, v.Z) for v in f.Vertices]
    except Exception:
        pts = {}
        for e in f.Edges:
            for v in (e.StartVertex, e.EndVertex):
                if v is not None:
                    pts[v.Id] = (v.X, v.Y, v.Z)
        return list(pts.values())


geo = ExtAPI.DataModel.GeoData
for asm in geo.Assemblies:
    for part in asm.Parts:
        for body in part.Bodies:
            for f in body.Faces:
                vs = face_vertices(f)
                faces.append((f.Id, vs, f.Area))
allv = [p for _, vs, _ in faces for p in vs]
lo = [min(p[i] for p in allv) for i in range(3)]
hi = [max(p[i] for p in allv) for i in range(3)]
diag = math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3)))


def pick_model():
    best, bm, bs = None, None, None
    for m in cfg["models"]:
        b0, b1 = m["bbox_mm"]
        d = math.sqrt(sum((b1[i] - b0[i]) ** 2 for i in range(3)))
        for s in (1.0, 1000.0, 0.001, 25.4, 1 / 25.4):
            if abs(diag * s - d) / d < 0.03:
                c = [(lo[i] + hi[i]) / 2 * s for i in range(3)]
                cm = [(b0[i] + b1[i]) / 2 for i in range(3)]
                e = math.sqrt(sum((c[i] - cm[i]) ** 2 for i in range(3)))
                if best is None or e < best:
                    best, bm, bs = e, m, s
    return bm, bs


mdl, SCALE = pick_model()
if MODEL_ID:
    mm = [m for m in cfg["models"] if m["id"] == MODEL_ID]
    if not mm:
        raise Exception("MODEL_ID %s not in %s" % (MODEL_ID, CONFIG))
    if mdl is None or mdl["id"] != MODEL_ID:
        log("WARNING: the geometry looks like %s, MODEL_ID = %s is used" % (mdl and mdl["id"], MODEL_ID))
    mdl = mm[0]
    if SCALE is None:
        SCALE = 1.0
if mdl is None:
    raise Exception("The geometry does not match any model of rtc7_fea.json (bbox diag %.4g)" % diag)
log("RTC-7: model %s, geometry scale to mm = %g, %d faces" % (mdl["id"], SCALE, len(faces)))


def match(sel, vs):
    if not vs:
        return False
    i = AX[sel["axis"]]
    c = sel["center"]
    pts = [[p[j] * SCALE for j in range(3)] for p in vs]
    rad = [math.sqrt(sum((p[j] - c[j]) ** 2 for j in range(3) if j != i)) for p in pts]
    if sel["type"] == "plane":
        return (all(abs(p[i] - sel["coord"]) < TOL for p in pts) and all(r >= sel["r_min"] - TOL for r in rad)
                and all(r <= sel["r_max"] + TOL for r in rad))
    a = [p[i] for p in pts]
    return (all(abs(r - sel["radius"]) < TOL for r in rad) and all(x >= sel["a_min"] - TOL for x in a)
            and all(x <= sel["a_max"] + TOL for x in a) and (max(a) - min(a)) > 0.5)


def select(role):
    itf = mdl[role]
    ids, area = [], 0.0
    for fid, vs, A in faces:
        if any(match(s, vs) for s in itf["selectors"]):
            ids.append(fid)
            area += A * SCALE * SCALE
    if not ids:
        raise Exception("%s %s: no faces found by the rules" % (mdl["id"], role))
    exp = itf["area_mm2"]
    log("  %s (%s): %d faces, area %.0f mm2 (expected %.0f)" % (role, itf["name"], len(ids), area, exp))
    if abs(area - exp) > 0.02 * exp:
        log("  WARNING: %s area differs from the expected one by more than 2 %% - check NS_%s" % (role, role.upper()))
    sel = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    sel.Ids = ids
    ns = Model.AddNamedSelection()
    ns.Location = sel
    ns.Name = "NS_%s_%s" % (role.upper(), itf["name"])
    return ns


ns_fix = select("fixed")
ns_load = select("load")

# ---------------------------------------------------------------- material, mesh
mats = [m.Name for m in Model.Materials.Children]
for b in Model.Geometry.GetChildren(DataModelObjectCategory.Body, True):
    if "AMg6" in mats:
        b.Material = "AMg6"
    else:
        log("WARNING: material AMg6 not in Engineering Data (%s) - assign it by hand" % ", ".join(mats))
Model.Mesh.ElementSize = q(float(mdl["mesh_mm"]), "mm")

# ---------------------------------------------------------------- analysis, steps, loads
an = Model.Analyses[0]
cases = mdl["cases"]
n = len(cases)
st = an.AnalysisSettings
st.NumberOfSteps = n
for i in range(n):
    try:
        st.SetStepEndTime(i + 1, q(float(i + 1), U_TIME))
    except Exception:
        pass

fs = an.AddFixedSupport()
fs.Location = ns_fix
fs.Name = "Fixed_" + mdl["fixed"]["name"]

rp = Model.AddRemotePoint()
rp.Location = ns_load
rp.Name = "RP_" + mdl["load"]["name"]
c = mdl["load"]["center"]
rp.XCoordinate = q(c[0], "mm")
rp.YCoordinate = q(c[1], "mm")
rp.ZCoordinate = q(c[2], "mm")
try:
    rp.Behavior = LoadBehavior.Rigid
except Exception:
    log("WARNING: set the Remote Point behaviour to Rigid by hand")


def tabular(comp, values, unit):
    comp.Inputs[0].DiscreteValues = [q(float(t), U_TIME) for t in range(n + 1)]
    comp.Output.DiscreteValues = [q(0.0, unit)] + [q(float(v), unit) for v in values]


rf = an.AddRemoteForce()
rf.Location = rp
rf.DefineBy = LoadDefineBy.Components
rf.Name = "Force_" + mdl["load"]["name"]
mo = an.AddMoment()
mo.Location = rp
mo.DefineBy = LoadDefineBy.Components
mo.Name = "Moment_" + mdl["load"]["name"]
ac = an.AddAcceleration()
ac.DefineBy = LoadDefineBy.Components
ac.Name = "Acceleration_part"
for k, comp in enumerate(("XComponent", "YComponent", "ZComponent")):
    tabular(getattr(rf, comp), [cs["F_N"][k] for cs in cases], "N")
    tabular(getattr(mo, comp), [cs["M_Nmm"][k] for cs in cases], U_MOM)
    tabular(getattr(ac, comp), [cs["acc_mm_s2"][k] for cs in cases], U_ACC)

# coordinate system at the fixed interface centre - the moment reaction is summed there
csys = Model.CoordinateSystems.AddCoordinateSystem()
csys.Name = "CS_fixed_" + mdl["fixed"]["name"]
cf = mdl["fixed"]["center"]
try:
    try:
        csys.OriginDefineBy = GeometryDefineByType.Coordinates
    except Exception:
        pass
    csys.OriginX = q(cf[0], "mm")
    csys.OriginY = q(cf[1], "mm")
    csys.OriginZ = q(cf[2], "mm")
except Exception:
    log("WARNING: could not place %s - moment reaction is summed at the default point" % csys.Name)

# ---------------------------------------------------------------- results per case
sol = an.Solution
res = []
for i, cs in enumerate(cases):
    t = q(float(i + 1), U_TIME)
    es = sol.AddEquivalentStress()
    es.Name = "Seqv %s" % cs["name"]
    es.DisplayTime = t
    td = sol.AddTotalDeformation()
    td.Name = "Def %s" % cs["name"]
    td.DisplayTime = t
    fr = sol.AddForceReaction()
    fr.BoundaryConditionSelection = fs
    fr.Name = "Freac %s" % cs["name"]
    fr.DisplayTime = t
    mr = sol.AddMomentReaction()
    mr.BoundaryConditionSelection = fs
    mr.Name = "Mreac %s" % cs["name"]
    mr.DisplayTime = t
    for setter in (lambda: setattr(mr, "Summation", MomentsAtSummationPointType.OrientationSystem),
                   lambda: setattr(mr, "Orientation", csys),
                   lambda: setattr(mr, "LocationMethod", LocationDefinitionMethod.CoordinateSystem),
                   lambda: setattr(mr, "CoordinateSystemSelection", csys)):
        try:
            setter()
        except Exception:
            pass
    res.append((cs, es, td, fr, mr))
log("RTC-7: %s set up - %d load steps (%s)" % (mdl["id"], n, ", ".join(cs["name"] for cs in cases)))


def val(x, unit):
    try:
        return x.ConvertToUnit(unit).Value
    except Exception:
        try:
            return float(x.Value)
        except Exception:
            return float("nan")


def comps(r, unit):
    out = []
    for a in ("XAxis", "YAxis", "ZAxis"):
        try:
            out.append(val(getattr(r, a), unit))
        except Exception:
            out.append(float("nan"))
    return out


if SOLVE:
    sol.Solve(True)
    Sy = float(cfg["material"]["Sy_MPa"])
    lines = ["model;case;sigma_eqv_max_MPa;sigma_allow_MPa;SF_yield;SF_required;status;deform_max_mm;"
             "Freac_x;Freac_y;Freac_z;Freac_exp_x;Freac_exp_y;Freac_exp_z;Mreac_x_Nmm;Mreac_y_Nmm;Mreac_z_Nmm;"
             "Mreac_exp_x;Mreac_exp_y;Mreac_exp_z"]
    for cs, es, td, fr, mr in res:
        s = val(es.Maximum, "MPa")
        d = val(td.Maximum, "mm")
        F = comps(fr, "N")
        M = comps(mr, U_MOM)
        sf = Sy / s if s > 0 else float("inf")
        ok = "OK" if sf >= cs["sf_required"] else "CHECK"
        lines.append(";".join([mdl["id"], cs["name"]] + ["%.2f" % v for v in (s, cs["sigma_allow_MPa"], sf, cs["sf_required"])]
                              + [ok, "%.3f" % d] + ["%.1f" % v for v in F + cs["reaction_F_N"]]
                              + ["%.0f" % v for v in M + cs["reaction_M_Nmm"]]))
        log("  %s: sigma_max %.1f MPa, SF %.2f (required %g) %s; reaction F %s N (expected %s)"
            % (cs["name"], s, sf, cs["sf_required"], ok, ["%.0f" % v for v in F], ["%.0f" % v for v in cs["reaction_F_N"]]))
    out = os.path.join(os.path.dirname(CONFIG), "results_%s.csv" % mdl["id"])
    f = open(out, "w")
    f.write("\n".join(lines) + "\n")
    f.close()
    log("RTC-7: results -> %s (max stress includes the peaks at the support edges - look at the plots)" % out)

lf = open(os.path.join(os.path.dirname(CONFIG), "log_%s.txt" % mdl["id"]), "w")
lf.write("\n".join(LOGLINES) + "\n")
lf.close()
