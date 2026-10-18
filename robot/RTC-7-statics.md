# RTC-7: static gravity torques (`python tools/robot_statics.py robot/RTC-7-layout.txt`)

Gravity only (no accelerations), worst pose over all angles of J2..J7 (no joint limits yet).
Payload centre of mass 100 mm beyond the flange. Reducer efficiency eta = 0.8.

## Mass model

| Body | Mass, kg | Moves with |
|---|---|---|
| J2 housing+motor | 16.08 | link 1 |
| J2 output shaft | 2.48 | link 2 |
| J3 housing+motor | 10.07 | link 2 |
| J3 output shaft | 3.12 | link 3 |
| J4 housing+motor | 10.07 | link 3 |
| J4 output shaft | 3.12 | link 4 |
| J5 housing+motor | 3.95 | link 4 |
| J5 output shaft | 1.23 | link 5 |
| J6 housing+motor | 3.95 | link 5 |
| J6 output shaft | 1.23 | link 6 |
| J7 housing+motor | 2.27 | link 6 |
| J7 output shaft | 0.69 | link 7 |
| link 2 bracket | 2.00 | link 2 |
| link 3 tube D120x5, 1086 mm | 5.30 | link 3 |
| link 3 fitting (low) | 1.50 | link 3 |
| link 3 fitting (high) | 1.50 | link 3 |
| link 4 bracket | 1.50 | link 4 |
| link 5 tube D100x4, 990 mm | 3.23 | link 5 |
| link 5 fitting (low) | 1.00 | link 5 |
| link 5 fitting (high) | 1.00 | link 5 |
| link 6 bracket | 0.80 | link 6 |
| **total moving above J2** | **76.1** | |

- SHM-1000: reducer mass not in the catalog, ESTIMATED 17.3 kg (steel x 0.6)
- links are ASSUMED (aluminium tubes and fittings, `LINKS` in the script) until they are designed

## Worst static torques

| Joint | Drive | Self-weight, N·m | Per 1 kg payload, N·m/kg | With 5 kg, N·m | Reducer rated / start-stop, N·m | Payload at rated torque, kg | Ratio needed (motor rated) |
|---|---|---|---|---|---|---|---|
| J1 | SHM-150m | 0 | 0.0 | 0 | 103 / 155 | - | - |
| J2 | SHM-1000 | 697 | 27.3 | 824 | 784 / 1960 | 3.2 | 114 -> 121 (n_out 3 rpm) |
| J3 | SHM-500 | 179 | 14.2 | 250 | 375 / 675 | 13.8 | 57 -> 59 (n_out 24 rpm) |
| J4 | SHM-500 | 149 | 14.0 | 217 | 375 / 675 | 16.1 | 49 -> 59 (n_out 24 rpm) |
| J5 | SHM-150 | 18 | 2.8 | 33 | 103 / 155 | 31.0 | 28 -> 29 (n_out 84 rpm) |
| J6 | SHM-150 | 5 | 2.6 | 18 | 103 / 155 | 38.3 | 15 -> 21 (n_out 116 rpm) |
| J7 | SHM-60 | 0 | 0.0 | 0 | 62 / 93 | - | - |

Static payload limit at the reducer rated torque: **3.2 kg**, set by J2.
J1 axis is vertical: no gravity torque, it carries only the inertia (and the ОПУ takes the tilting moment).
Dynamic loads (accelerations) come on top; start-stop torque is the catalog limit for them.

Worst poses (deg, J1..J7):

- J2: 0, 82, 90, -0, -180, 0, -61
- J3: 0, 90, -124, -90, 180, -0, 61
- J4: 0, -2, -180, -85, 90, 0, -172
- J5: 0, -13, -172, -102, 18, 90, 144
- J6: 0, 90, 0, 0, 0, 0, 0
- J7: 0, -37, -159, 71, 77, -72, -94
