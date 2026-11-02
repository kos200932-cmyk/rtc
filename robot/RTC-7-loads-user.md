# RTC-7 user configuration: joint loads (`python tools/user_loads.py`), 2026-10-27

Payload 8 kg 200 mm beyond the TCP (SZU end face) + SZU 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses (J2 ±90°, J4 ±170°, others ±180°). Moving mass (without payload, on the ОПУ): 114.8 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) |
|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 4.0 | 37 (62, 59 %) | 1042 (ОПУ) | 1221 (ОПУ) | 27 | RI70-KV95 | 79 | 0.58 (0.94) |
| J2 | 80E | 25.1 | 988 (1400, 71 %) | 453 (2156, 21 %) | 21 (-) | 905 | AK80-9-V3-KV100 | 153 | 8.08 (9) |
| J3 | KB50 | 20.0 | 320 (415, 77 %) | 947 (1032, 92 %) | 627 (11200, 6 %) | 638 | RI115-PH-KV40 | 99 | 4.04 (5.5) |
| J4 | KB45 | 15.0 | 314 (375, 84 %) | 314 (740, 42 %) | 356 (10200, 3 %) | 359 | RI115-PH-KV40 | 79 | 4.97 (5.5) |
| J5 | KB32 | 6.0 | 63 (103, 61 %) | 277 (336, 82 %) | 247 (8800, 3 %) | 251 | RI70-KV95 | 79 | 1.00 (0.94) |
| J6 | KB25 | 3.5 | 52 (62, 84 %) | 52 (194, 27 %) | 155 (5300, 3 %) | 158 | RI70-KV95 | 49 | 1.33 (0.94) |
| J7 | KB17 | 1.8 | 0 (23, 0 %) | 31 (48, 64 %) | 124 (2600, 5 %) | 124 | RI70-KV95 | 21 | 0.00 (0.94) |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 12.3 kN against C0 135 kN (s0 = 11.0).
