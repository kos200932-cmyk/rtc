# RTC-7: joint line-up with the axes kept (reducer = 60 % of the joint mass) - `python tools/layout_select.py --reach 2400`

Payload 8 kg (100 mm beyond the flange) + interface 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses in the joint ranges, payload within 2400 mm of the J1 axis. Reducer loaded to <= 90 % of T_rated / M_tilt / F_axial. Catalog `components/DMRD/KB-series.txt`; fixed: J2=80E. Motor: rated torque x ratio x eta 0.8 (loaded to <= 90 % too). Moving mass (without payload, J1 excluded): 125.9 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) | Motor speed, rpm (AK80-9: after its 9:1) | Worst pose: payload r / z, mm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 3.8 | 38 (62, 61 %) | 1104 (ОПУ) | 1331 (ОПУ) | 28 | RI70-KV95 | 59 | 0.80 (0.94) | 113 | 2349 / 1239 |
| J2 | 80E | 38.3 | 1097 (1400, 78 %) | 444 (2156, 21 %) | 23 (-) | 952 | AK80-9-V3-KV100 | 153 | 8.97 (9 x9) | 292 | 2394 / 48 |
| J3 | KB50 | 25.2 | 342 (415, 82 %) | 905 (1032, 88 %) | 663 (11200, 6 %) | 676 | RI115-PH-KV40 | 99 | 4.32 (5.5) | 189 | 1797 / 471 |
| J4 | KB45 | 17.3 | 303 (375, 81 %) | 313 (740, 42 %) | 376 (10200, 4 %) | 378 | RI115-PH-KV40 | 79 | 4.79 (5.5) | 151 | 1323 / 1504 |
| J5 | KB32 | 6.8 | 50 (103, 49 %) | 258 (336, 77 %) | 260 (8800, 3 %) | 261 | RI70-KV95 | 79 | 0.80 (0.94) | 151 | 2263 / 819 |
| J6 | KB25 | 3.8 | 32 (62, 52 %) | 33 (194, 17 %) | 156 (5300, 3 %) | 159 | RI70-KV95 | 49 | 0.82 (0.94) | 94 | 2257 / 1475 |
| J7 | KB14 | 1.3 | 0 (10, 0 %) | 10 (20, 48 %) | 126 (1600, 8 %) | 128 | RI70-KV95 | 21 | 0.00 (0.94) | 40 | 803 / 242 |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 13.0 kN against C0 135 kN (s0 = 10.4).

