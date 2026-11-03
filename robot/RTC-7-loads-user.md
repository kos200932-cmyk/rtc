# RTC-7 user configuration: joint loads (`python tools/user_loads.py`), 2026-10-27

Payload 8 kg 200 mm beyond the TCP (SZU end face) + SZU 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses (J2 ±90°, J4 ±170°, others ±180°). Moving mass (without payload, on the ОПУ): 109.7 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) |
|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 4.0 | 35 (62, 56 %) | 997 (ОПУ) | 1170 (ОПУ) | 25 | RI70-KV95 | 79 | 0.55 (0.94) |
| J2 | 80E | 25.1 | 949 (1400, 68 %) | 409 (2156, 19 %) | 20 (-) | 854 | AK80-9-V3-KV100 | 153 | 7.75 (9) |
| J3 | KB50 | 20.0 | 284 (415, 68 %) | 911 (1032, 88 %) | 576 (11200, 5 %) | 587 | RI115-PH-KV40 | 99 | 3.58 (5.5) |
| J4 | KB45 | 15.0 | 279 (375, 74 %) | 279 (740, 38 %) | 321 (10200, 3 %) | 324 | RI115-PH-KV40 | 99 | 3.52 (5.5) |
| J5 | KB32 | 6.0 | 57 (103, 55 %) | 244 (336, 73 %) | 233 (8800, 3 %) | 236 | RI70-KV95 | 99 | 0.71 (0.94) |
| J6 | KB25 | 3.5 | 52 (62, 84 %) | 52 (194, 27 %) | 155 (5300, 3 %) | 158 | RI70-KV95 | 99 | 0.66 (0.94) |
| J7 | KB17 | 1.8 | 0 (23, 0 %) | 31 (48, 64 %) | 124 (2600, 5 %) | 124 | RI70-KV95 | 21 | 0.00 (0.94) |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 11.7 kN against C0 135 kN (s0 = 11.5).
