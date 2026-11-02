# LINK-4U (user's link J4-J5, 30ХГСА, 4.87 kg) - quick stiffness / strength check, CalculiX tet10, 2026-11-02

`python tools/fea_link_quick.py links-user/LINK-4U/LINK-4U.txt --out fea/link4u --h 6 --E 210000 --name link4u
 --fixed "x0:-0.5..3.5|rx:88,75,0,39.5..79.5" --load "y0:-0.5..0.5|ry:85,75,0,69.5..86" --center 85,0,75 --case ...`

Fixed: the recess D158 x 3 (face x=3 + wall) on the J4 output (KB45). Load: rigid body on the J5 flange face (y=0,
annulus D140..D172), centre on the J5 axis (85, 0, 75). Worst J5 loads of robot/RTC-7-loads-user.md (2026-11-02,
link 4 = 4.87 kg): torque 63 N*m about the J5 axis, tilting 277 N*m at the J5 output + Fr 251 N x 56.5 mm = 291 N*m at
the flange, axial 247 N, radial 251 N - all together. Mesh h 6 on 12 / 10 mm plates (49 k nodes).

| Case | u ref, mm (x y z) | rot, mrad (x y z) | vM max / far, MPa |
|---|---|---|---|
| A: tilt about X (across both axes) + T + Fa + Fr | 0.000 / 0.000 / 0.001 | 0.016 / -0.008 / -0.002 | 9.7 / 4.4 |
| B: tilt about Z (in the plane of both axes) + T + Fa + Fr | 0.001 / 0.002 / 0.000 | -0.003 / 0.006 / 0.030 | 19.4 / 3.8 |
| torque 63 N*m only | 0 | -0.003 / 0.006 / 0.000 | 3.1 / 0.8 |
| unit Mx 100 N*m | 0 | 0.006 / -0.004 / 0 | 3.5 / 1.5 |
| unit Mz 100 N*m | 0.001 | 0 / 0 / 0.011 | 6.8 / 1.3 |

Strength: 19.4 MPa peak (edge of the fixed set) against sigma_y 30ХГСА >= 835 MPa -> n ~ 43.
Stiffness: worst rotation of the J5 seat 0.030 mrad -> ~0.04 mm at the TCP (lever ~1.3 m) - negligible.
Compliance: ~0.11 mrad per kN*m (tilt in the plane of the axes), ~0.07 mrad per kN*m across.

TCP deflection, rigid joints (budget of 2026-10-26, 11.0 mm, scaled by the gravity moment x lever of each link in the
stretched horizontal pose, tools: scratch sag_ratio, state before / after LINK-4U): links 1-3 and the ОПУ -4.4 %
(the arm is 32.5 mm shorter, link 4 4.87 kg vs 6.84 kg of the v2 link it replaces), link 5 unchanged:
link 3 4.49, link 2 2.36, link 5 2.0, link 1 1.20, ОПУ 0.48, link 4 0.04, other 0.03 -> ~10.6 mm (was 11.0).

## Lightening variants (2026-11-02, same loads, h 4.5; outer faces x=0..3 / y=0 kept, plates thinned inward)

Windows in the gussets: triangle offset 15 mm from the plates and the diagonal edge (corners R10 in the "r" variants).

| Variant | plate J4 / plate J5 / gussets, mm | windows | mass, kg | rot J5 seat, mrad (A / B) | vM max / far, MPa (B) | TCP, mm |
|---|---|---|---|---|---|---|
| V0 (current) | 12 / 12 / 10 | - | 4.87 | 0.016 / 0.030 | 21 / 5 | 0.04 |
| V1 | 12 / 12 / 6 | sharp | 3.30 | 0.025 / 0.122 | 42 / 33 | 0.16 |
| V5 | 8 / 8 / 10 | sharp | 3.00 | 0.037 / 0.143 | 50 / 33 | 0.19 |
| V4r | 10 / 8 / 6 | R10 | 2.74 | 0.033 / 0.137 | 50 / 36 | 0.19 |
| V2r | 8 / 8 / 6 | R10 | 2.41 | 0.040 / 0.165 | 55 / 40 | 0.23 |
| V3 | 8 / 8 / 5 | sharp | 2.23 | 0.041 / 0.213 | 64 / 54 | 0.29 |

All n >= 13 vs 835 MPa. The lighter link also unloads links 1-3 and the ОПУ: -2.5 kg at ~1.4 m = -34 N*m (-3.7 %) ->
about -0.3 mm at the TCP, so V2r / V4r give a net TCP change of about -0.1 mm (10.6 -> ~10.5 mm).
With plate J5 8 mm the M5 holes are 8 deep (through); plate J4 8 leaves 5 mm under the M8 heads (recess 3) -> V4r keeps 7.

ACCEPTED (user 2026-11-02): V4r -> links-user/LINK-4U/LINK-4U.txt (2.74 kg), loads robot/RTC-7-loads-user.md recomputed.
