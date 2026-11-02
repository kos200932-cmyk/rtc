# RTC-7 user configuration: joint loads (`python tools/user_loads.py`), 2026-10-27

Payload 8 kg 200 mm beyond the TCP (SZU end face) + SZU 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses (J2 ±90°, J4 ±170°, others ±180°). Moving mass (without payload, on the ОПУ): 112.6 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) |
|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 4.0 | 36 (62, 58 %) | 1009 (ОПУ) | 1199 (ОПУ) | 26 | RI70-KV95 | 79 | 0.57 (0.94) |
| J2 | 80E | 25.1 | 960 (1400, 69 %) | 443 (2156, 21 %) | 21 (-) | 883 | AK80-9-V3-KV100 | 153 | 7.84 (9) |
| J3 | KB50 | 20.0 | 315 (415, 76 %) | 920 (1032, 89 %) | 605 (11200, 5 %) | 616 | RI115-PH-KV40 | 99 | 3.98 (5.5) |
| J4 | KB45 | 15.0 | 311 (375, 83 %) | 312 (740, 42 %) | 335 (10200, 3 %) | 337 | RI115-PH-KV40 | 79 | 4.93 (5.5) |
| J5 | KB32 | 6.0 | 54 (103, 52 %) | 276 (336, 82 %) | 246 (8800, 3 %) | 250 | RI70-KV95 | 79 | 0.85 (0.94) |
| J6 | KB25 | 3.5 | 52 (62, 84 %) | 52 (194, 27 %) | 155 (5300, 3 %) | 158 | RI70-KV95 | 49 | 1.33 (0.94) |
| J7 | KB17 | 1.8 | 0 (23, 0 %) | 31 (48, 64 %) | 124 (2600, 5 %) | 124 | RI70-KV95 | 21 | 0.00 (0.94) |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 11.9 kN against C0 135 kN (s0 = 11.4).
