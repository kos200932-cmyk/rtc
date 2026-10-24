# LINK-1U (user's J1-J2 link, 30ХГСА) - quick FEA, CalculiX tet10 h 4.5 (147 k nodes), 2026-10-23

Spec links-user/LINK-1U/LINK-1U.txt (+16 x D9 on D206 for the 80E flange), part frame: X = J1 axis (up),
Z = J2 axis. E 210 GPa. Mass 9.70 kg (7850 kg/m3).
Fixed: base bottom face on the flange of the adapter "Юла" (x=-135, r 57..80 from the J1 axis) + bore D115 on its tube.
Load: rigid body on the 80E flange face (z=0, r 95..111 from the J2 axis) + bore D190, about the J2 output face
centre (0, 0, 54). Worst J2 loads from robot/RTC-7-loads-v2 (steel LINK-2): J2 torque 1212 N·m, tilting 479 N·m,
radial 1019 N; + J2 joint weight 25.1 kg (246 N at 50 mm from the J1 axis). Gravity = -X.

| Case | rot x / y / z, mrad | u max, mm | vM peak / away, MPa | n = 835 / peak |
|---|---|---|---|---|
| W1: Mz 1212 + My +479 + Fx -1019 + weight | 0.09 / 0.14 / 0.17 | 0.02 | 86 / 53 | 9.7 |
| W2: Mz 1212 + My -479 + Fx -1019 + weight | 0.09 / -0.17 / 0.17 | 0.02 | 96 / 64 | 8.7 |
| W3: Mz 1212 + Mx 479 + Fy 1019 + weight | 0.16 / 0.00 / 0.23 | 0.02 | 91 / 54 | 9.2 |
| unit Mz 1 kN·m (J2 torque) | 0.08 / - / 0.14 | | 63 / 33 | |
| unit My 1 kN·m | - / 0.33 / - | | 105 / 105 | |
| unit Mx 1 kN·m | 0.15 / - / 0.08 | | 63 / 27 | |
| unit Fx -1 kN | - / 0.02 / - | | 8 / 6 | |

Peaks: inner corner base / gusset (x=-117, y=+-112, z=-128) and base / plate. TCP lever ~2.6 m from J2:
max ~0.23 mrad -> ~0.6 mm. Masses (30ХГСА): LINK-1U 9.70 kg, "Юла" 1.80 kg, "Пластина переходная" 2.46 kg.

## Lighter variants (2026-10-24, tools/gen_link1u.py; specs links-user/LINK-1U/variants/), same loads, h 4
J1 housing only held against turning (user) - does not change the loads of this link.

| Variant | plate / base / gusset, mm | window offset base+plate / bottom | mass, kg | max rot, mrad | TCP ~2.6 m, mm | vM peak / away | n (835 / peak) |
|---|---|---|---|---|---|---|---|
| current | 18 / 18 / 10 | 12 / 30 | 9.70 | 0.23 | 0.6 | 111 / 67 | 7.5 |
| V1 | 12 / 14 / 8 | 12 / 25 | 6.87 | 0.42 | 1.1 | 179 / 104 | 4.7 |
| **V2** | 10 / 12 / 6 | 10 / 20 | 5.45 | 0.65 | 1.7 | 234 / 159 | 3.6 |
| V3 | 8 / 12 / 5 | 10 / 20 | 4.87 | 0.84 | 2.2 | 243 / 168 | 3.4 |

Base >= 12: 12 x M8 threaded in it (engagement 1.5 d). Peaks: inner corner base / gusset bottom and base / plate.
