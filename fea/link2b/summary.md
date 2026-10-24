# LINK-2B (user's box, J2-J3.STEP 2026-10-24) + J3 SHM-KB50F - strength, 2026-10-24

Material 30ХГСА (quenched + tempered): σт >= 835 MPa, σв >= 1080 MPa, E 210 GPa, ρ 7850. Mass 9.84 kg.
CalculiX tet10, h 4.5 mm (156 k nodes). Fixed: the J2 output contact - pocket bottom z=14 (r <= 80) + pocket wall D160.
Load: rigid body on the J3 seat - plate bottom under the flange D236 (y=1, r 107..118) + bore D214 (y 1..19), reference
point = J3 output face (0, 70, 150). Loads = worst J3 loads of robot/RTC-7-loads-v2 (the arm beyond J3 is the v2 one):
tilting 989 N·m, torque 347 N·m, axial 691 N (pulls J3 off the plate), radial 704 N, applied together.

| Case | rot x / y / z, mrad | vM max | vM away from the boundary sets (where) | n = 835 / vM max |
|---|---|---|---|---|
| W1: Mx +989 (tilt along the J2 axis) + My 347 + Fy -691 + Fz 704 | 0.56 / 0.01 / 0.00 | 160 | 84 (wall/plate corner x=±120, y=-35, z=26) | 5.2 |
| W1-: Mx -989, Fz -704 | 0.48 / 0.01 / 0.00 | 144 | 72 | 5.8 |
| W2: Mz 989 (J2 torque direction) + My 347 + Fy -691 + Fx 704 | 0.04 / 0.01 / 0.06 | 53 | 25 | 15.7 |
| W3: Mx 700 + Mz 700 + My 347 + Fy -691 + Fx, Fz 500 | 0.41 / 0.01 / 0.04 | 125 | 67 | 6.7 |
| W4: Mx -700 + Mz 700 ... | 0.33 / 0.01 / 0.04 | 112 | 55 | 7.5 |

vM max sits on the boundary sets (fixed / load faces, stress singularities of the rigid ties). Weld zone, conservatively
0.7 σт = 585 MPa: n >= 3.6. J2 torque up to 1212 N·m (v2) -> W2 x 1.23: ~65 MPa. Stiffness: 0.56 mrad at the J3 face
(TCP lever ~2.2 m -> ~1.2 mm), 3.6 x stiffer than the accepted LINK-2 (2.0 mrad).

## Screws
- J3 flange D236 -> plate, 24 x M5 8.8 on D224, thread in the plate (18): tilting at the flange plane 989 + 704·0.069 =
  1038 N·m -> 2M/(n r) = 772 N + axial 29 N = 0.80 kN per screw (external). Preload 8.8 M5 ~6.2 kN (MA ~5.9 N·m): no
  opening, screw ~6.3 kN = 445 MPa < 640 (Rp0.2) -> n 1.4 on yield at full preload, 8 x on the external load.
  Torque 347 N·m + radial 704 N -> 3.8 kN at r 112: friction 0.15 x 24 x 5.4 kN = 19 kN (n 5), plus the D214 fit.
  NOTE: thread M5 on r 112 is only 2.5 mm from the bore D214 (r 107) - drill/tap after boring, no chamfer > 0.5 on the bore.
  Bearing under DIN912 M5 heads (D8.5) on the flange of the motor housing: 6.3 kN / 33 mm2 = 190 MPa - with Д16Т
  flange use hardened washers (or steel flange).
- Reducer ring -> flange D236, 12 x M8 8.8 on D200 from the ring face into the flange (16): 2 x 1038 / (12 x 0.1) =
  1.73 kN + 0.06 kN per screw vs preload ~16 kN -> OK.
