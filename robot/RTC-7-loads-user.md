# RTC-7 user configuration: joint loads (`python tools/user_loads.py`), 2026-10-27

Payload 8 kg 200 mm beyond the TCP (SZU end face) + SZU 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses (J2 ±90°, J4 ±170°, others ±180°). Moving mass (without payload, on the ОПУ): 116.7 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) |
|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 4.0 | 38 (62, 61 %) | 1075 (ОПУ) | 1241 (ОПУ) | 27 | RI70-KV95 | 79 | 0.60 (0.94) |
| J2 | 80E | 25.1 | 1021 (1400, 73 %) | 466 (2156, 22 %) | 22 (-) | 925 | AK80-9-V3-KV100 | 153 | 8.34 (9) |
| J3 | KB50 | 20.0 | 330 (415, 80 %) | 978 (1032, 95 %) | 647 (11200, 6 %) | 658 | RI115-PH-KV40 | 99 | 4.17 (5.5) |
| J4 | KB45 | 15.0 | 324 (375, 86 %) | 324 (740, 44 %) | 376 (10200, 4 %) | 379 | RI115-PH-KV40 | 79 | 5.12 (5.5) |
| J5 | KB32 | 6.0 | 63 (103, 62 %) | 277 (336, 83 %) | 247 (8800, 3 %) | 251 | RI70-KV95 | 79 | 1.00 (0.94) |
| J6 | KB25 | 3.5 | 52 (62, 84 %) | 52 (194, 27 %) | 155 (5300, 3 %) | 159 | RI70-KV95 | 49 | 1.33 (0.94) |
| J7 | KB17 | 1.8 | 0 (23, 0 %) | 31 (48, 64 %) | 125 (2600, 5 %) | 124 | RI70-KV95 | 21 | 0.00 (0.94) |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 12.7 kN against C0 135 kN (s0 = 10.7).
