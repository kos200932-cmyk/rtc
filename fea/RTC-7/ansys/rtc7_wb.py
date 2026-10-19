# encoding: utf-8
# RTC-7 link strength - Workbench 2024 R1 project script (IronPython). ASCII only on purpose.
#
#   Workbench: File > Scripting > Run Script File... > rtc7_wb.py
#
# Creates one Static Structural system per model of rtc7_fea.json (LINK-1 ... LINK-6, LINK-1A), material AMg6
# in its Engineering Data, the STEP geometry, then opens Mechanical for every system and runs rtc7_mech.py
# there (interfaces, loads, mesh, results, solve), saves the project RTC7_links.wbpj next to this folder.
#
# Settings:
FEA_DIR = r""          # folder with rtc7_fea.json; "" = the folder of this script's parent (fea\RTC-7)
ONLY = []              # e.g. ["LINK-3"] - only these models; [] = all
SOLVE = True           # False: set up only, solve later in Mechanical
import os
import json

if not FEA_DIR:
    try:
        FEA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        FEA_DIR = os.getcwd()
CONFIG = os.path.join(FEA_DIR, "rtc7_fea.json")
MECH = os.path.join(FEA_DIR, "ansys", "rtc7_mech.py")
if not os.path.isfile(CONFIG):
    raise Exception("rtc7_fea.json not found in %s - set FEA_DIR at the top of rtc7_wb.py" % FEA_DIR)
cfg = json.load(open(CONFIG))
mat = cfg["material"]


def refresh(system, names=("Engineering Data", "Geometry")):
    """bring the upstream cells up to date - otherwise Workbench stops with
    'The following components need attention before proceeding: Engineering Data'"""
    for n in names:
        try:
            c = system.GetComponent(Name=n)
            try:
                c.Refresh()
            except Exception:
                pass
            c.Update(AllDependencies=True)
        except Exception as e:
            print("%s: %s update: %s" % (system.DisplayText, n, e))


def add_material(system):
    """AMg6 in the Engineering Data of the system (if the calls differ in the installed version, add it by hand:
    Density, Isotropic Elasticity, Tensile Yield / Ultimate Strength - values in rtc7_fea.json)."""
    try:
        ed = system.GetContainer(ComponentName="Engineering Data")
        m = ed.CreateMaterial(Name="AMg6")
        p = m.CreateProperty(Name="Density", Qualifiers={"Definition": "", "Behavior": ""})
        p.SetData(Index=-1, Variables=["Density"], Values=[["%g [kg m^-3]" % mat["rho"]]])
        p = m.CreateProperty(Name="Elasticity", Behavior="Isotropic", Qualifiers={"Definition": "", "Behavior": "Isotropic"})
        p.SetData(Index=-1, Variables=["Young's Modulus", "Poisson's Ratio"],
                  Values=[["%g [MPa]" % mat["E_MPa"], "%g" % mat["nu"]]])
        p = m.CreateProperty(Name="Tensile Yield Strength", Qualifiers={"Definition": "", "Behavior": ""})
        p.SetData(Index=-1, Variables=["Tensile Yield Strength"], Values=[["%g [MPa]" % mat["Sy_MPa"]]])
        p = m.CreateProperty(Name="Tensile Ultimate Strength", Qualifiers={"Definition": "", "Behavior": ""})
        p.SetData(Index=-1, Variables=["Tensile Ultimate Strength"], Values=[["%g [MPa]" % mat["Su_MPa"]]])
        return True
    except Exception as e:
        print("AMg6 not created automatically: %s" % e)
        return False


template = GetTemplate(TemplateName="Static Structural", Solver="ANSYS")
done = []
prev = None
for m in cfg["models"]:
    if ONLY and m["id"] not in ONLY:
        continue
    if prev is None:
        system = template.CreateSystem()
    else:
        system = template.CreateSystem(Position="Below", RelativeTo=prev)
    system.DisplayText = m["id"]
    add_material(system)
    geom = system.GetContainer(ComponentName="Geometry")
    geom.SetFile(FilePath=os.path.join(FEA_DIR, m["step"].replace("/", os.sep)))
    refresh(system)
    try:
        system.GetComponent(Name="Model").Refresh()
    except Exception:
        pass
    model = system.GetContainer(ComponentName="Model")
    model.Edit()
    cmd = ("CONFIG = r'%s'\nMODEL_ID = '%s'\nSOLVE = %s\nexec(open(r'%s').read())\n"
           % (CONFIG, m["id"], "True" if SOLVE else "False", MECH))
    try:
        model.SendCommand(Language="Python", Command=cmd)
    except Exception as e:
        print("%s: Mechanical script failed (%s) - run rtc7_mech.py by hand in Mechanical "
              "(Automation > Scripting), MODEL_ID = '%s'" % (m["id"], e, m["id"]))
    try:
        model.Exit()
    except Exception:
        pass
    done.append(m["id"])
    prev = system

Save(FilePath=os.path.join(FEA_DIR, "RTC7_links.wbpj"), Overwrite=True)
print("RTC-7: systems %s; results_<model>.csv in %s" % (", ".join(done), FEA_DIR))
