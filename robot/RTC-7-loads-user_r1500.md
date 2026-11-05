# RTC-7 user configuration: joint loads (`python tools/user_loads.py`), 2026-10-27

Payload 8 kg 200 mm beyond the TCP (SZU end face) + SZU 4 kg; all joints at ±0.2 rad/s, ±0.1 rad/s²; worst of 40000 random poses (J2 ±90°, J4 ±170°, others ±180°). Moving mass (without payload, on the ОПУ): 109.7 kg.
Payload zone: the payload is carried only while the TCP is within R1500 from the J1 axis; beyond it - SZU only.


| Joint | Reducer | Joint mass, kg | Torque, N·m (rated) | Tilting, N·m (allow.) | Axial, N (allow.) | Radial, N | Motor | Ratio | Motor torque, N·m (rated) |
|---|---|---|---|---|---|---|---|---|---|
| J1 | KB25 | 4.0 | 25 (62, 41 %) | 776 (ОПУ) | 1168 (ОПУ) | 24 | RI70-KV95 | 79 | 0.40 (0.94) |
| J2 | 80E | 25.1 | 726 (1400, 52 %) | 385 (2156, 18 %) | 20 (-) | 852 | AK80-9-V3-KV100 | 153 | 5.93 (9) |
| J3 | KB50 | 20.0 | 281 (415, 68 %) | 690 (1032, 67 %) | 576 (11200, 5 %) | 584 | RI115-PH-KV40 | 99 | 3.55 (5.5) |
| J4 | KB45 | 15.0 | 276 (375, 74 %) | 278 (740, 38 %) | 320 (10200, 3 %) | 321 | RI115-PH-KV40 | 99 | 3.49 (5.5) |
| J5 | KB32 | 6.0 | 56 (103, 54 %) | 239 (336, 71 %) | 234 (8800, 3 %) | 233 | RI70-KV95 | 99 | 0.71 (0.94) |
| J6 | KB25 | 3.5 | 51 (62, 83 %) | 52 (194, 27 %) | 153 (5300, 3 %) | 156 | RI70-KV95 | 99 | 0.65 (0.94) |
| J7 | KB17 | 1.8 | 0 (23, 0 %) | 31 (48, 64 %) | 123 (2600, 5 %) | 123 | RI70-KV95 | 21 | 0.00 (0.94) |

J1 ОПУ RU178G: P0 = Fr + 2M/Dp + 0.44 Fa = 9.3 kN against C0 135 kN (s0 = 14.6).
