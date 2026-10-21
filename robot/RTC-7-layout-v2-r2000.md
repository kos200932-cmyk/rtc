# RTC-7: joint line-up with the axes kept (reducer = 60 % of the joint mass; known: J2=25.08 kg) - `python tools/layout_select.py --reach 2000`

Payload 8 kg (100 mm beyond the flange) + interface 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses in the joint ranges, payload within 2000 mm of the J1 axis. Reducer loaded to <= 90 % of T_rated / M_tilt / F_axial. Catalog `components/DMRD/KB-series.txt`; fixed: J2=80E. Motor: rated torque x ratio x eta 0.8 (loaded to <= 90 % too). Moving mass (without payload, J1 excluded): 112.6 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) | Motor speed, rpm (AK80-9: after its 9:1) | Worst pose: payload r / z, mm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 3.8 | 34 (62, 55 %) | 1029 (ОПУ) | 1200 (ОПУ) | 29 | RI70-KV95 | 59 | 0.72 (0.94) | 113 | 1909 / 2088 |
| J2 | 80E | 25.1 | 1015 (1400, 73 %) | 436 (2156, 20 %) | 23 (-) | 934 | AK80-9-V3-KV100 | 153 | 8.30 (9 x9) | 292 | 1986 / 935 |
| J3 | KB50 | 25.2 | 345 (415, 83 %) | 822 (1032, 80 %) | 664 (11200, 6 %) | 675 | RI115-PH-KV40 | 99 | 4.36 (5.5) | 189 | 1878 / 635 |
| J4 | KB45 | 17.3 | 301 (375, 80 %) | 307 (740, 41 %) | 374 (10200, 4 %) | 376 | RI115-PH-KV40 | 79 | 4.76 (5.5) | 151 | 1671 / 1487 |
| J5 | KB32 | 6.8 | 50 (103, 49 %) | 256 (336, 76 %) | 260 (8800, 3 %) | 261 | RI70-KV95 | 79 | 0.80 (0.94) | 151 | 1877 / 21 |
| J6 | KB25 | 3.8 | 32 (62, 52 %) | 33 (194, 17 %) | 156 (5300, 3 %) | 158 | RI70-KV95 | 49 | 0.82 (0.94) | 94 | 1361 / -153 |
| J7 | KB14 | 1.3 | 0 (10, 0 %) | 10 (20, 48 %) | 127 (1600, 8 %) | 127 | RI70-KV95 | 21 | 0.00 (0.94) | 40 | 1738 / 1630 |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 12.1 kN against C0 135 kN (s0 = 11.1).

