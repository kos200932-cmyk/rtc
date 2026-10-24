# BASEPLATE (Д16Т, 0.87 kg) - bearing (смятие) check, hand calculation, 2026-10-24

Д16Т plate: σ0.2 ~ 290 MPa, σв ~ 420 MPa; allowable bearing in a fixed joint taken [σсм] ~ 0.6 σ0.2 = 175 MPa;
allowable flank pressure of a thread in aluminium ~ 100 MPa (common design value).
Loads: ОПУ - tilting 1239 N·m, axial 1277 N (robot/RTC-7-loads-v2); J1 torque 135 N·m (KB25 momentary max);
bolts 12 x M8 on D217 (8 through + 4 threaded), preload ~17 kN (10.9) unless noted; 12 x M4 on D120 ~3.5 kN.

| Place | Value | Allowable | n |
|---|---|---|---|
| under the ОПУ outer ring (annulus D182..D240 minus holes, 18 460 mm2): preload 11.1 + moment 1.4 + axial 0.1 | 12.5 MPa (local at bolts ~2-3x -> ~35 MPa) | 175 | 5..14 |
| under the KB25 flange (D112..D136, 4 675 mm2), 12 x M4 preload | 9.0 MPa | 175 | 19 |
| thread M8 x 10 in the plate, flank pressure at 17 kN / 14 kN / 12 kN | 139 / 115 / 98 MPa | ~100 | 0.7 / 0.9 / 1.0 |
| thread M8 x 10, stripping (shear) at 17 kN | 90 MPa | ~0.6 σв = 250 | 2.8 |
| thread M4 x 8, flank pressure at 3.5 kN | 73 MPa | ~100 | 1.4 |
| hole walls D9 / M4 under the J1 torque if the friction slips (104 N / 188 N) | 1.3 / 5.9 MPa | 175 | >30 |

Result: the plate itself is far from bearing failure; the weak point are the 4 x M8 threads 10 long in Д16Т -
tighten for ~12 kN (8.8, ~20 N·m) or use thread inserts (Heli-Coil M8, length 1.5 d), or through bolts with nuts.
Note: with 12 x M4 the J1 housing is bolted rigidly to the plate - this does not match "J1 housing held only against
turning"; for that the M4 joint must be replaced by an anti-rotation pin / torque arm free in tilt and axially.

## Decision (user, 2026-10-24)
- 4 x M8 threaded in the plate: tightening limited - preload <= 12 kN (class 8.8, T ~ 0.2 * 12 kN * 8 mm ~ 19 N·m);
  flank pressure 98 MPa (~ allowable). Joint opening under the tilting moment: max external load per bolt on D217
  1239 N·m * 108.5 / (6 * 108.5^2) ~ 1.9 kN << 12 kN - no gap. The 8 through bolts with nuts keep the full preload.
- J1 anti-rotation decoupling (instead of the rigid 12 x M4): later.
