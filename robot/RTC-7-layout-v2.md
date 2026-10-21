# RTC-7: joint line-up with the axes kept (reducer = 60 % of the joint mass; known: J1=4, J2=25.1, J3=20, J4=15, J5=6, J6=3.5, J7=1.3 kg) - `python tools/layout_select.py`

Payload 8 kg (100 mm beyond the flange) + interface 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses in the joint ranges. Reducer loaded to <= 90 % of T_rated / M_tilt / F_axial. Catalog `components/DMRD/KB-series.txt`; fixed: J2=80E. Motor: rated torque x ratio x eta 0.8 (loaded to <= 90 % too). Moving mass (without payload, J1 excluded): 103.9 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) | Motor speed, rpm (AK80-9: after its 9:1) | Worst pose: payload r / z, mm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 4.0 | 38 (62, 62 %) | 1099 (ОПУ) | 1116 (ОПУ) | 28 | RI70-KV95 | 59 | 0.81 (0.94) | 113 | 2399 / 1319 |
| J2 | 80E | 25.1 | 1081 (1400, 77 %) | 419 (2156, 19 %) | 22 (-) | 849 | AK80-9-V3-KV100 | 153 | 8.83 (9 x9) | 292 | 2740 / 59 |
| J3 | KB50 | 20.0 | 331 (415, 80 %) | 908 (1032, 88 %) | 617 (11200, 6 %) | 629 | RI115-PH-KV40 | 99 | 4.17 (5.5) | 189 | 1880 / -46 |
| J4 | KB45 | 15.0 | 302 (375, 81 %) | 307 (740, 41 %) | 358 (10200, 4 %) | 360 | RI115-PH-KV40 | 79 | 4.79 (5.5) | 151 | 2781 / 216 |
| J5 | KB32 | 6.0 | 50 (103, 48 %) | 255 (336, 76 %) | 253 (8800, 3 %) | 256 | RI70-KV95 | 79 | 0.79 (0.94) | 151 | 2277 / 1062 |
| J6 | KB25 | 3.5 | 32 (62, 51 %) | 33 (194, 17 %) | 157 (5300, 3 %) | 158 | RI70-KV95 | 49 | 0.81 (0.94) | 94 | 2231 / 588 |
| J7 | KB14 | 1.3 | 0 (10, 0 %) | 10 (20, 48 %) | 127 (1600, 8 %) | 128 | RI70-KV95 | 21 | 0.00 (0.94) | 40 | 1575 / 2098 |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 12.9 kN against C0 135 kN (s0 = 10.5).

