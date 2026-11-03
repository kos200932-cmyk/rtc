# TCP deflection, rigid joints - `python tools/tcp_stiffness.py --q 0,90,0,0,0,0,0`

Pose q = 0,90,0,0,0,0,0 deg (J2 90 = the arm stretched horizontally), TCP reach 2576 mm, height 171 mm.
Payload 8 kg 200 mm beyond the TCP + SZU 4 kg; link self-weight included (CalculiX GRAV).
Each link: fixed on its proximal seat (rigid joint), the weight of everything after it on its distal seat (rigid body).

| Link | card | load, kg | moment at the seat, N·m | seat rotation, mrad | vM max / far, MPa | TCP, mm (vertical) | TCP, mm (total) |
|---|---|---|---|---|---|---|---|
| L1 | `links-user/LINK-1U/LINK-1U.txt` | 110.5 | 925 | 0.434 | 115 / 49 | -0.89 | 1.11 |
| L2 | `links-user/LINK-2B/LINK-2B.txt` | 78.2 | 922 | 0.161 | 76 / 34 | -0.41 | 0.41 |
| L3 | `links-user/LINK-3U/LINK-3U.txt` | 46.8 | 272 | 3.136 | 20 / 19 | -6.35 | 6.35 |
| L4 | `links-user/LINK-4U/LINK-4U.txt` | 29.0 | 247 | 0.041 | 19 / 8 | -0.04 | 0.04 |
| L5 | `links-user/LINK-5U/LINK-5U.txt` | 18.7 | 52 | 2.529 | 15 / 15 | -2.16 | 2.16 |
| ОПУ | K 5.4e+06 N·m/rad | - | 938 | 0.174 | - | -0.44 | 0.45 |

**TCP: 10.32 mm total, -10.30 mm vertical** (link 6, Юла, plate, joints not included: rigid / ~0.05 mm).

## Second pose: q = 0,90,90,0,0,0,0 (J3 90 - J4 axis vertical, wrist loaded across)
| Link | card | load, kg | moment at the seat, N·m | seat rotation, mrad | vM max / far, MPa | TCP, mm (vertical) | TCP, mm (total) |
|---|---|---|---|---|---|---|---|
| L1 | `links-user/LINK-1U/LINK-1U.txt` | 110.5 | 932 | 0.447 | 117 / 50 | -0.91 | 1.12 |
| L2 | `links-user/LINK-2B/LINK-2B.txt` | 78.2 | 920 | 0.163 | 75 / 35 | -0.42 | 0.42 |
| L3 | `links-user/LINK-3U/LINK-3U.txt` | 46.8 | 271 | 3.134 | 20 / 19 | -6.34 | 6.34 |
| L4 | `links-user/LINK-4U/LINK-4U.txt` | 29.0 | 246 | 0.124 | 49 / 29 | -0.16 | 0.16 |
| L5 | `links-user/LINK-5U/LINK-5U.txt` | 18.7 | 50 | 2.480 | 15 / 15 | -2.08 | 2.12 |
| ОПУ | K 5.4e+06 N·m/rad | - | 950 | 0.176 | - | -0.45 | 0.45 |

**TCP: 10.38 mm total, -10.35 mm vertical** (link 6, Юла, plate, joints not included: rigid / ~0.05 mm).

## Stiffening estimate (tubes; bending of the tube dominates the link rotation)
Link 3 D120x5 -> D160x6: I 2.99e6 -> 8.02e6 mm4 (x2.7): 6.35 -> ~2.4 mm; link 5 D80x4 -> D100x5: I 0.545e6 -> 1.69e6 (x3.1): 2.16 -> ~0.7 mm.
Total ~4.9 mm; with the static deflection compensated in the control (85 %) -> ~0.7 mm.
