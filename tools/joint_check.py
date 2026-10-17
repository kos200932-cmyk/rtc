#!/usr/bin/env python3
"""Check joint descriptions (joints/*/*.txt) against component cards (components/**.txt).

Run from the repo root:   python tools/joint_check.py [--eta 0.8] [--out joints/STATUS.md]

Checks:
  * every USE file exists and every JOIN/OUT reference to a component port exists in its card;
  * torque: which reducer ratio is needed to reach T_nom from the motor rated / peak torque
    (with an assumed reducer efficiency eta); if the ratio is known - output torque and speed;
  * lists every value still marked '?' (what has to be filled in).
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def strip(line):
    return re.split(r"[#;]", line, maxsplit=1)[0].strip()


def num(v):
    try:
        return float(v.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def read_card(path):
    """Component card: COMPONENT name, TYPE, DATA k=v..., PORT name x dir k=v..."""
    card = {"name": None, "type": None, "data": {}, "ports": {}, "path": path}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            t = strip(raw).split()
            if not t:
                continue
            kw = t[0].upper()
            if kw == "COMPONENT":
                card["name"] = t[1]
            elif kw == "TYPE":
                card["type"] = t[1]
            elif kw == "DATA":
                for kv in t[1:]:
                    k, _, v = kv.partition("=")
                    card["data"][k] = v
            elif kw == "PORT":
                params = dict(kv.partition("=")[::2] for kv in t[4:] if "=" in kv)
                card["ports"][t[1]] = {"x": t[2], "dir": t[3], **params}
    return card


def read_joint(path):
    j = {"name": None, "data": {}, "use": {}, "design": [], "join": [], "out": {}, "path": path}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            t = strip(raw).split()
            if not t:
                continue
            kw = t[0].upper()
            if kw == "JOINT":
                j["name"] = t[1]
            elif kw == "DATA":
                for kv in t[1:]:
                    k, _, v = kv.partition("=")
                    j["data"][k] = v
            elif kw == "USE":
                j["use"][t[1]] = {"component": t[2], "file": t[3] if len(t) > 3 else None}
            elif kw == "DESIGN":
                j["design"].append(t[1])
            elif kw == "JOIN":
                j["join"].append((t[1], t[2]))
            elif kw == "OUT":
                j["out"][t[1]] = t[2]
    return j


def check_joint(j, eta):
    problems, todo, cards = [], [], {}
    for role, u in j["use"].items():
        if u["component"] == "?":
            todo.append(f"{role}: component not chosen")
            continue
        p = os.path.join(ROOT, u["file"] or "")
        if not u["file"] or not os.path.isfile(p):
            problems.append(f"{role}: file not found {u['file']}")
            continue
        c = read_card(p)
        cards[role] = c
        for k, v in c["data"].items():
            if v == "?":
                todo.append(f"{c['name']}: DATA {k}")
        for pn, pd in c["ports"].items():
            if pd["x"] == "?" or "?" in pd.values():
                todo.append(f"{c['name']}: PORT {pn}")

    refs = [r for pair in j["join"] for r in pair] + list(j["out"].values())
    for r in refs:
        owner, _, port = r.partition(".")
        if owner in j["design"]:
            continue  # part designed for this joint - its ports are created by the generator
        if owner not in j["use"]:
            problems.append(f"unknown owner '{owner}' in {r}")
        elif owner in cards and port not in cards[owner]["ports"]:
            problems.append(f"{cards[owner]['name']} has no PORT '{port}' ({r})")

    res = {"T_nom": num(j["data"].get("T_nom"))}
    m, red = cards.get("motor"), cards.get("reducer")
    if m:
        d = m["data"]
        res.update(motor=m["name"], T_rated=num(d.get("T_rated")), T_peak=num(d.get("T_peak")),
                   n_rated=num(d.get("n_rated")), pre_ratio=num(d.get("ratio")) or 1.0)
        if res["T_nom"]:
            res["i_peak"] = res["T_nom"] / (res["T_peak"] * eta)
            res["i_rated"] = res["T_nom"] / (res["T_rated"] * eta)
    if red:
        i = num(red["data"].get("ratio"))
        rd = red["data"]
        res.update(reducer=red["name"], ratio=i, R_rated=num(rd.get("T_rated")),
                   R_ss=num(rd.get("T_startstop")), R_peak=num(rd.get("T_peak")))
        if i and m:
            res["T_out_rated"] = res["T_rated"] * i * eta
            res["T_out_peak"] = res["T_peak"] * i * eta
            res["n_out"] = res["n_rated"] / i
    return res, problems, todo


def fmt(v, nd=0):
    return "?" if v is None else f"{v:.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eta", type=float, default=0.8, help="assumed reducer efficiency")
    ap.add_argument("--out", help="write the report to this markdown file")
    a = ap.parse_args()

    jdir = os.path.join(ROOT, "joints")
    files = sorted((os.path.join(dp, f) for dp, _, fs in os.walk(jdir) for f in fs
                    if f.endswith(".txt")),
                   key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p)])
    lines = [f"# Joint check (`python tools/joint_check.py`)", "",
             f"Assumed reducer efficiency eta = {a.eta}. Torques in N*m, speeds in rpm.",
             "Required ratio = T_nom / (motor torque x eta); for an actuator the motor torque is already after its own gearbox.", "",
             "Reducer T: catalog rated / start-stop / momentary max at the output.", "",
             "| Joint | Reducer | Motor | T_nom | Reducer T rated / start-stop / max | Motor T rated / peak | Ratio needed: from peak / from rated | Reducer ratio | T_out rated / peak | n_out |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    details, bad = [], False
    for f in files:
        j = read_joint(f)
        r, problems, todo = check_joint(j, a.eta)
        lines.append(
            f"| {j['name']} | {r.get('reducer', '?')} | {r.get('motor', '?')} | {fmt(r['T_nom'])} | "
            f"{fmt(r.get('R_rated'))} / {fmt(r.get('R_ss'))} / {fmt(r.get('R_peak'))} | "
            f"{fmt(r.get('T_rated'), 2)} / {fmt(r.get('T_peak'), 2)} | "
            f"{fmt(r.get('i_peak'), 1)} / {fmt(r.get('i_rated'), 1)} | {fmt(r.get('ratio'))} | "
            f"{fmt(r.get('T_out_rated'))} / {fmt(r.get('T_out_peak'))} | {fmt(r.get('n_out'), 1)} |")
        details.append(f"\n## {j['name']}\n")
        details += [f"- ERROR: {p}" for p in problems] or ["- links: OK"]
        details += [f"- to fill: {t}" for t in todo]
        bad |= bool(problems)
    report = "\n".join(lines + details) + "\n"
    print(report)
    if a.out:
        with open(os.path.join(ROOT, a.out), "w", encoding="utf-8") as fh:
            fh.write(report)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
