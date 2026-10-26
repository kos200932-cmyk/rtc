# Links 3-6 (links-v2, AlMg, E 71 GPa) - quick stiffness / strength check, CalculiX tet10, 2026-10-25

Fixed: the face + centring skirt on the previous joint output; load: rigid body on the next joint seat (face + bore),
worst loads of the next joint from robot/RTC-7-loads-v2 applied together (torque + tilting + axial + radial).

| Link | h, mm | loads at the seat | u ref, mm (x y z) | rot, mrad (x y z) | vM max / far, MPa |
|---|---|---|---|---|---|
| LINK-3 (tube D120x5) | 8 | J4: T 310, tilt 316 N*m, Fa 408, Fr 411 N (case A) | 1.53 / -0.85 / 0.30 | 1.62 / 2.46 / -0.03 | 19.9 / 19.9 |
| LINK-4 | 7 | J5: T 51, tilt 257 N*m, Fa 257, Fr 260 N | 0.00 / 0.00 / 0.00 | 0.00 / 0.02 / 0.00 | 6.2 / 2.5 |
| LINK-5 (tube D80x4) | 8 | J6: T 32, tilt 33 N*m, Fa 159, Fr 161 N (case A) | 1.48 / -0.31 / -0.30 | 0.64 / 2.53 / 0.00 | 13.0 / 11.9 |
| LINK-6 | 4.5 | J7: tilt 10 N*m, Fa 127, Fr 128 N | 0.00 / 0.00 / 0.00 | 0.01 / 0.01 / 0.01 | 2.2 / 2.2 |

TCP contribution (u + rot x lever to TCP; worst loads): LINK-3 ~5.9 mm, LINK-5 ~2.2 mm, LINK-4 0.03, LINK-6 ~0.
Report (strength + stiffness, TCP budget, TCP 1 mm plan): Claude doc "RTC-7: отчёт по прочности и жёсткости".
Meshes coarse (h 7..8 on 4..5 mm walls, tet10): stiffness ok to ~10 %, stresses indicative.
