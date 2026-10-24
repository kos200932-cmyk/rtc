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

## Stiffness budget of the J1-J2-J3 chain (worst loads of robot/RTC-7-loads-v2, each at its own worst pose - upper bound)
| Element | load | rotation, mrad | TCP (lever ~2.4-2.6 m), mm |
|---|---|---|---|
| ОПУ RU178 (K ~5.4e6 N·m/rad) | tilting 1239 N·m | 0.23 | 0.6 |
| LINK-1U V2 (30ХГСА) | J2 loads | 0.61 | 1.6 |
| J2 80E torsion (K 196 N·m/arcmin = 6.7e5 N·m/rad) | 1212 N·m | 1.80 | 4.3 |
| J2 80E lost motion 1 arcmin | - | 0.29 | 0.7 |
| J2 80E tilting (K 1176 N·m/arcmin) | 479 N·m | 0.12 | 0.3 |
| **LINK-2B (30ХГСА, 9.84 kg)** | J3 loads | **0.56** | **1.3** |
| J3 KB50 | 989 N·m tilting / 347 N·m | no catalog stiffness | ? |
The J2 reducer torsion dominates; LINK-2B is ~15 % of the budget -> it can be lightened.

## Mass reduction study (specs fea/link2b/LINK-2B-A|B|C.txt), same loads, h 4.5
| Variant | walls / shelf / plate outside D190 / shelf chamfers | mass, kg | W1 rot, mrad | vM max / far, MPa | n = 835 / max | weld 585 / max |
|---|---|---|---|---|---|---|
| current LINK-2B | 10 / 18 / 24 / 50x50 | 9.84 | 0.56 | 160 / 84 | 5.2 | 3.7 |
| A | 6 / 14 / 24 / 50x50 | 8.18 | 0.85 | 210 / 122 | 4.0 | 2.8 |
| **B** (recommended) | 6 / 14 / 14 (z 0..10 removed outside D190) / 60x74 | **7.27** | 1.17 | 255 / 146 | 3.3 | 2.3 |
| C | 6 / 12 / 14 / 60x74 | 6.96 | 1.42 | 288 / 176 | 2.9 | 2.0 |
Hot spot in every variant: inner corner wall / plate at the lower wall end (x=±120, y=-35, z=25) - add fillet R8..10
(or a fillet weld leg 6) there, as on LINK-1U. Shelf >= 14: the M5 thread needs >= 10 (2 d) of engagement.

## ACCEPTED (2026-10-24): variant B + fillets R8 wall / plate (links-user/LINK-2B/LINK-2B.txt), 7.29 kg
| Case | rot x / y / z, mrad | vM max / far, MPa | n = 835 / max | weld 585 / far |
|---|---|---|---|---|
| W1 Mx+ | 1.13 / 0.01 / 0.00 | 257 / 102 (fillet end x=120, y=-34) | 3.2 | 5.7 |
| W3 Mx Mz | 0.82 / 0.01 / 0.06 | 199 / 86 | 4.2 | 6.8 |
The fillets take the hot spot down from 146 to 102 MPa; the max sits on the boundary (tie) sets. TCP ~2.6 mm.
No interference in the J1..J4 assembly (tools/gen_user_l123.py).

Edit 2026-10-24: side walls end at z 200 (start of the shelf chamfer, they stuck out 24 mm past it) -> 7.17 kg.

## Shelf 14 -> 8 (user 2026-10-24): links-user/LINK-2B/LINK-2B.txt, 6.25 kg, h 4 mm
| Case | rot x / y / z, mrad | vM max / far, MPa | n = 835 / max | weld 585 / far |
|---|---|---|---|---|
| W1 Mx+ | 1.92 / 0.01 / 0.00 | 274 / 173 (fillet end x=120, y=-35, z=29) | 3.0 | 3.4 |
| W1 Mx- | 1.64 / 0.01 / 0.00 | 242 / 147 | 3.4 | 4.0 |
| W2 Mz | 0.14 / 0.01 / 0.21 | 132 / 74 | 6.3 | 7.9 |
| W3 Mx Mz | 1.40 / 0.01 / 0.15 | 241 / 136 | 3.5 | 4.3 |
Stiffness: 1.92 mrad at the J3 face (~4.4 mm at the TCP) - now about as compliant as the J2 reducer in torsion (1.8 mrad).
M5 thread in 8 mm of 30ХГСА (1.6 d): stripping ~47 kN >> screw load 6.3 kN - OK; screws DIN912 M5x25 (flange 16 + 8
thread, 1 mm out above the shelf top - free space outside the ring D214).

## Shelf 10 (user 2026-10-24, "8 - stiffness not enough"): links-user/LINK-2B/LINK-2B.txt, 6.55 kg, h 4 mm
| Case | rot x / y / z, mrad | vM max / far, MPa | n = 835 / max | weld 585 / far |
|---|---|---|---|---|
| W1 Mx+ | 1.64 / 0.01 / 0.00 | 272 / 151 | 3.1 | 3.9 |
| W1 Mx- | 1.40 / 0.01 / 0.00 | 232 / 129 | 3.6 | 4.5 |
| W2 Mz | 0.12 / 0.01 / 0.15 | 120 / 53 | 7.0 | 11 |
| W3 Mx Mz | 1.19 / 0.01 / 0.11 | 238 / 118 | 3.5 | 5.0 |
Shelf 8 / 10 / 14: 1.92 / 1.64 / 1.13 mrad (W1). Screws DIN912 M5x25 (flange 16 + 9 in the 10 mm thread).
