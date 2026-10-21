# RTC-7: joint line-up with the axes kept (reducer = 60 % of the joint mass; known: J1=4, J2=25.1, J3=20, J4=15, J5=6, J6=3.5, J7=1.3 kg) - `python tools/layout_select.py --reach 2000`

Payload 8 kg (100 mm beyond the flange) + interface 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses in the joint ranges, payload within 2000 mm of the J1 axis. Reducer loaded to <= 90 % of T_rated / M_tilt / F_axial. Catalog `components/DMRD/KB-series.txt`; fixed: J2=80E. Motor: rated torque x ratio x eta 0.8 (loaded to <= 90 % too). Moving mass (without payload, J1 excluded): 103.9 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) | Motor speed, rpm (AK80-9: after its 9:1) | Worst pose: payload r / z, mm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 4.0 | 33 (62, 53 %) | 965 (ОПУ) | 1114 (ОПУ) | 28 | RI70-KV95 | 49 | 0.83 (0.94) | 94 | 1909 / 2088 |
| J2 | 80E | 25.1 | 953 (1400, 68 %) | 417 (2156, 19 %) | 22 (-) | 847 | AK80-9-V3-KV100 | 153 | 7.78 (9 x9) | 292 | 1986 / 935 |
| J3 | KB50 | 20.0 | 337 (415, 81 %) | 778 (1032, 75 %) | 617 (11200, 6 %) | 628 | RI115-PH-KV40 | 99 | 4.26 (5.5) | 189 | 1863 / 530 |
| J4 | KB45 | 15.0 | 295 (375, 79 %) | 301 (740, 41 %) | 356 (10200, 3 %) | 359 | RI115-PH-KV40 | 79 | 4.68 (5.5) | 151 | 1671 / 1487 |
| J5 | KB32 | 6.0 | 50 (103, 48 %) | 252 (336, 75 %) | 254 (8800, 3 %) | 255 | RI70-KV95 | 79 | 0.79 (0.94) | 151 | 1877 / 21 |
| J6 | KB25 | 3.5 | 32 (62, 51 %) | 33 (194, 17 %) | 154 (5300, 3 %) | 157 | RI70-KV95 | 49 | 0.81 (0.94) | 94 | 1361 / -153 |
| J7 | KB14 | 1.3 | 0 (10, 0 %) | 10 (20, 48 %) | 127 (1600, 8 %) | 127 | RI70-KV95 | 21 | 0.00 (0.94) | 40 | 1738 / 1630 |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 11.4 kN against C0 135 kN (s0 = 11.9).

