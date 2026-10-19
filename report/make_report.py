#!/usr/bin/env python3
"""Build the ГОСТ 7.32 report in two passes: docx -> PDF (LibreOffice) -> heading pages -> docx with the contents
page numbers and the page count in the abstract.   python report/make_report.py"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SOFFICE = "/root/.claude/skills/synced/72af9e33-207a-4d30-84f2-2734733088fd_a108db8c-a87e-4219-b444-3c9a563d8a81/docx/scripts/office/soffice.py"
DOCX = os.path.join(HERE, "RTC-7_otchet_NIR.docx")
PDF = os.path.join(HERE, "RTC-7_otchet_NIR.pdf")
META = os.path.join(HERE, "pages.json")


def build(meta):
    if meta:
        json.dump(meta, open(META, "w"), ensure_ascii=False, indent=1)
    subprocess.run(["node", os.path.join(HERE, "build_report.js")] + ([META] if meta else []), check=True)
    subprocess.run(["python3", SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", HERE, DOCX], check=True,
                   capture_output=True)


def pages_text():
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", PDF], capture_output=True, text=True).stdout).group(1))
    out = []
    for p in range(1, n + 1):
        t = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", PDF, "-"], capture_output=True, text=True).stdout
        out.append(re.sub(r"\s+", " ", t))
    return out


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def locate(entries, pages):
    toc_page = next(i for i, t in enumerate(pages) if "СОДЕРЖАНИЕ" in t)
    res, start = {}, toc_page + 1
    for e in entries:
        key = norm(e)
        if key.startswith("Приложение "):                      # appendix heading: "ПРИЛОЖЕНИЕ А"
            letter = key.split()[1]
            probe = f"ПРИЛОЖЕНИЕ {letter}"
        else:
            probe = key[:40]
        for i in range(start, len(pages)):
            if probe in pages[i]:
                res[e] = i + 1
                start = i
                break
        else:
            print("not found:", e)
    return res


build(None)
entries = json.load(open(os.path.join(HERE, "toc_entries.json"), encoding="utf-8"))
for it in range(3):
    pages = pages_text()
    meta = {"pages": len(pages), "toc": locate(entries, pages)}
    build(meta)
    pages2 = pages_text()
    meta2 = {"pages": len(pages2), "toc": locate(entries, pages2)}
    if meta2 == meta:
        break
print("pages", meta2["pages"])
for k, v in meta2["toc"].items():
    print(f"  {v:3d}  {k}")
