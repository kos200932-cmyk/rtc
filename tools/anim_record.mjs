// Frame-by-frame recording of the motion viewer (robot/anim/*-viewer.html) -> PNG frames -> MP4 / GIF.
//
//   node tools/anim_record.mjs robot/anim/RTC-7-viewer.html out_dir [--w 1920 --h 1080 --step 1]
//        [--stills stills.json] [--modules path/to/node_modules]   (playwright + three@0.147.0)
//   ffmpeg -framerate 30 -i out_dir/f%04d.png -c:v libx264 -pix_fmt yuv420p -crf 20 RTC-7-demo.mp4
//
// The viewer is opened as  file://...#record  (no controls, big caption); three.js is served from the
// local node_modules instead of the CDN. Camera: slow orbit round the arm over the whole program.
import fs from "fs";
import path from "path";
import { createRequire } from "module";

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : d; };
const html = path.resolve(args[0]), out = path.resolve(args[1]);
const W = +opt("w", 1920), H = +opt("h", 1080), STEP = +opt("step", 1);
const mods = path.resolve(opt("modules", "node_modules"));
const require = createRequire(path.join(mods, "x.js"));
const { chromium } = require("playwright");
fs.mkdirSync(out, { recursive: true });

const exe = process.env.CHROME_EXE || (fs.existsSync("/opt/pw-browsers/chromium") ? "/opt/pw-browsers/chromium" : undefined);
const browser = await chromium.launch({ executablePath: exe, args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on("console", (m) => { if (m.type() === "error") console.log("page:", m.text()); });
await page.route("https://cdn.jsdelivr.net/npm/three@0.147.0/**", (r) => {
  const rel = r.request().url().split("three@0.147.0/")[1];
  r.fulfill({ path: path.join(mods, "three", rel), contentType: "application/javascript" });
});
await page.goto("file://" + html + "#record");
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
// fonts from local @fontsource packages (the sandbox has no Google Fonts)
const fdir = (pkg) => "file://" + path.join(mods, "@fontsource", pkg, "files");
let ff = "";
for (const [fam, pkg, ws] of [["Fira Sans Condensed", "fira-sans-condensed", [400, 500, 600]], ["IBM Plex Mono", "ibm-plex-mono", [400, 500]]])
  for (const w of ws) for (const sub of ["latin", "cyrillic"])
    if (fs.existsSync(path.join(mods, "@fontsource", pkg, "files", `${pkg}-${sub}-${w}-normal.woff2`)))
      ff += `@font-face{font-family:"${fam}";font-weight:${w};src:url("${fdir(pkg)}/${pkg}-${sub}-${w}-normal.woff2") format("woff2");}`;
if (ff) await page.addStyleTag({ content: ff });
await page.evaluate(async () => { await document.fonts.ready; await new Promise(r => setTimeout(r, 300)); });

const stillsPath = opt("stills", "");
if (stillsPath) {
  const stills = JSON.parse(fs.readFileSync(stillsPath, "utf-8"));
  for (const s of stills) {
    await page.evaluate((s) => window.__rtc.still(s.q, s), s);
    await page.screenshot({ path: path.join(out, s.name + ".png") });
    console.log("still", s.name);
  }
} else {
  const N = await page.evaluate(() => window.__rtc.frames);
  const tgt = [0, -350, 950];
  let k = 0;
  for (let i = 0; i < N; i += STEP) {
    const s = i / (N - 1);
    const az = (18 + 48 * s) * Math.PI / 180, el = (16 + 6 * Math.sin(s * Math.PI)) * Math.PI / 180, R = 5700;
    const cam = { pos: [tgt[0] + R * Math.cos(el) * Math.sin(az), tgt[1] - R * Math.cos(el) * Math.cos(az), tgt[2] + R * Math.sin(el)], target: tgt };
    await page.evaluate(([i, cam]) => window.__rtc.frame(i, cam), [i, cam]);
    await page.screenshot({ path: path.join(out, `f${String(k).padStart(4, "0")}.png`) });
    if (k % 100 === 0) console.log("frame", i, "/", N);
    k++;
  }
}
await browser.close();
