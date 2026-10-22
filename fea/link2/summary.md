# LINK-2 (angle bracket, J3 axis 135) - quick stiffness check, CalculiX tet10 (tools/fea_link_quick.py), 2026-10-22

Fixed: the face x=0 on the J2 output (r <= 93 from the J2 axis), all DOF. Load: rigid body on the J3 seat (counterbore
bottom z=365, r 88..107 + its wall D214) about the point (135, 0, 365). AlMg, E 71 GPa. Rotation of the J3 seat, mrad.

| Variant | mass, kg | Mx 1 kN·m (J2 torque direction): rot x / z, vM far | My 1 kN·m (arm leaning in XZ): rot y, vM far | Fz -700 N: rot y |
|---|---|---|---|---|
| current: shelves 14 / 16, gussets 65 (LINK-2.txt) | 4.29 | 1.16 / 1.52 mrad, 49 MPa | **33.0 mrad, 488 MPa** | 2.9 |
| + ribs 10 x 50 full height (y +-95, z 150..359) | 4.76 | 0.69 / 1.32, 61 | 4.6, 171 | 0.37 |
| + closed box (front wall x 54..64) | 5.43 | 0.60 / 0.91, 58 | 4.6, 201 | 0.37 |
| ribs + rim 24 above the shelf (outside D216) | 7.02 | 0.50 / 0.87, 37 | 4.2, 129 | 0.35 |
| web 25 below the J3 flange + ribs z 60..359 + rim | 8.36 | 0.39 / 0.45, 24 | 3.1, 109 | 0.25 |

TCP lever ~2.4 m: 1 mrad -> ~2.4 mm. J3 tilting moment at its face up to 989 N·m (any direction), J2 torque up to 1200 N·m.
Variant specs: fea/link2/LINK-2-ribs|box|rim|strong.txt.
