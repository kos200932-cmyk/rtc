# RTC-7 user configuration: joint loads (`python tools/user_loads.py`), 2026-11-18 (with the KWR90 F/T stack)

Payload 8 kg 200 mm beyond the TCP (SZU end face) + SZU 4 kg + F/T sensor KWR90 stack 0.70 kg (SZU +51 mm); all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 20000 random poses (J2 ±90°, J4 ±170°, others ±180°). Moving mass (without payload, on the ОПУ): 110.3 kg.

| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) |
|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 4.0 | 36 (62, 59 %) | 1020 (ОПУ) | 1178 (ОПУ) | 26 | RI70-KV95 | 79 | 0.58 (0.94) |
| J2 | 80E | 25.1 | 972 (1400, 69 %) | 425 (2156, 20 %) | 20 (-) | 862 | AK80-9-V3-KV100 | 153 | 7.94 (9) |
| J3 | KB50 | 20.0 | 299 (415, 72 %) | 934 (1032, 90 %) | 583 (11200, 5 %) | 594 | RI115-PH-KV40 | 99 | 3.77 (5.5) |
| J4 | KB45 | 15.0 | 294 (375, 78 %) | 294 (740, 40 %) | 328 (10200, 3 %) | 331 | RI115-PH-KV40 | 99 | 3.71 (5.5) |
| J5 | KB32 | 6.0 | 64 (103, 62 %) | 258 (336, 77 %) | 240 (8800, 3 %) | 243 | RI70-KV95 | 99 | 0.80 (0.94) |
| J6 | KB25 | 3.5 | 59 (62, 96 %) | 60 (194, 31 %) | 162 (5300, 3 %) | 165 | RI70-KV95 | 99 | 0.75 (0.94) |
| J7 | KB17 | 1.8 | 0 (23, 0 %) | 37 (48, 77 %) | 131 (2600, 5 %) | 131 | RI70-KV95 | 21 | 0.00 (0.94) |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 12.0 kN against C0 135 kN (s0 = 11.2).
