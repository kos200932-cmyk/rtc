# RTC-7: joint line-up with the axes kept (reducer = 60 % of the joint mass) - `python tools/layout_select.py`

Payload 8 kg (100 mm beyond the flange) + interface 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses in the joint ranges. Reducer loaded to <= 90 % of T_rated / M_tilt / F_axial. Catalog `components/DMRD/KB-series.txt`; fixed: J2=80E. Motor: rated torque x ratio x eta 0.8 (loaded to <= 90 % too). Moving mass (without payload, J1 excluded): 125.9 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) | Motor speed, rpm (AK80-9: after its 9:1) | Worst pose: payload r / z, mm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 3.8 | 40 (62, 64 %) | 1166 (ОПУ) | 1332 (ОПУ) | 30 | RI70-KV95 | 59 | 0.84 (0.94) | 113 | 2399 / 1319 |
| J2 | 80E | 38.3 | 1146 (1400, 82 %) | 440 (2156, 20 %) | 23 (-) | 952 | AK80-9-V3-KV100 | 153 | 9.36 (9 x9) | 292 | 2740 / 59 |
| J3 | KB50 | 25.2 | 341 (415, 82 %) | 954 (1032, 92 %) | 664 (11200, 6 %) | 676 | RI115-PH-KV40 | 99 | 4.30 (5.5) | 189 | 1841 / -234 |
| J4 | KB45 | 17.3 | 308 (375, 82 %) | 313 (740, 42 %) | 375 (10200, 4 %) | 378 | RI115-PH-KV40 | 79 | 4.88 (5.5) | 151 | 2781 / 216 |
| J5 | KB32 | 6.8 | 50 (103, 49 %) | 259 (336, 77 %) | 259 (8800, 3 %) | 262 | RI70-KV95 | 79 | 0.80 (0.94) | 151 | 2277 / 1062 |
| J6 | KB25 | 3.8 | 32 (62, 52 %) | 33 (194, 17 %) | 158 (5300, 3 %) | 159 | RI70-KV95 | 49 | 0.82 (0.94) | 94 | 2231 / 588 |
| J7 | KB14 | 1.3 | 0 (10, 0 %) | 10 (20, 48 %) | 127 (1600, 8 %) | 128 | RI70-KV95 | 21 | 0.00 (0.94) | 40 | 1575 / 2098 |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 13.7 kN against C0 135 kN (s0 = 9.8).

