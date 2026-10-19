# RTC-7: static gravity torques (`python tools/robot_statics.py robot/RTC-7-layout.txt`)

Gravity only (no accelerations), worst pose over all angles of J2..J7 (no joint limits yet).
Tool-change interface 4 kg always on the flange (COM 30 mm out); payload COM 100 mm beyond the flange. Reducer efficiency eta = 0.8.

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
| link 1: LINK-1-01_Weldment | 5.05 | link 1 |
| link 1: LINK-1-02_J1Adapter | 0.49 | link 1 |
| link 2: LINK-2-01_Weldment | 3.65 | link 2 |
| link 3: LINK-3-01_Weldment | 10.88 | link 3 |
| link 4: LINK-4-01_Weldment | 2.27 | link 4 |
| link 5: LINK-5-01_Weldment | 5.55 | link 5 |
| link 6: LINK-6-01_Weldment | 1.09 | link 6 |
| tool interface | 4.00 | link 7 |
| **total moving above J2** | **91.3** | |

- SHM-1000: reducer mass not in the catalog, ESTIMATED 17.3 kg (steel x 0.6)
- links: designed links `links/LINK-n` (OCC volume x density, real centres of mass)

## Worst static torques

| Joint | Drive | Self-weight, N·m | Per 1 kg payload, N·m/kg | With 8 kg, N·m | Reducer rated (T_design if set) / start-stop, N·m | Payload at rated torque, kg | Ratio needed (motor rated) |
|---|---|---|---|---|---|---|---|
| J1 | SHM-150m | 0 | 0.0 | 0 | 103 / 155 | - | - |
| J2 | SHM-1000 | 869 | 27.3 | 1075 | 1000 / 1960 | 4.8 | 149 -> 153 (n_out 3 rpm) |
| J3 | SHM-500 | 249 | 14.4 | 365 | 375 / 675 | 8.8 | 83 -> 99 (n_out 14 rpm) |
| J4 | SHM-500 | 217 | 14.0 | 326 | 375 / 675 | 11.3 | 74 -> 79 (n_out 18 rpm) |
| J5 | SHM-150 | 29 | 3.1 | 54 | 103 / 155 | 24.2 | 47 -> 49 (n_out 50 rpm) |
| J6 | SHM-150 | 13 | 2.6 | 33 | 103 / 155 | 35.3 | 29 -> 29 (n_out 84 rpm) |
| J7 | SHM-60 | 0 | 0.0 | 0 | 62 / 93 | - | - |

Static payload limit at the reducer rated torque: **4.8 kg**, set by J2.
J1 axis is vertical: no gravity torque, it carries only the inertia (and the ОПУ takes the tilting moment).
Dynamic loads (accelerations) come on top; start-stop torque is the catalog limit for them.

Worst poses (deg, J1..J7):

- J2: 0, 82, 90, -0, -180, 0, -61
- J3: 0, 90, -120, -90, 180, 1, 61
- J4: 0, -2, -180, -85, 90, 0, -172
- J5: 0, 95, 179, 5, -153, 90, 53
- J6: 0, 90, 0, 0, 0, 0, 0
- J7: 0, 99, -118, -37, -81, 7, -72

## Payload zones (static, rated torques; poses in the arm plane, best configuration)

- reach with 8 kg: flange up to 2495 mm from the J1 axis
- full reach (any payload >= 0): 2641 mm
- map: `robot/RTC-7-payload-zones.png`
