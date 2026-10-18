# RTC-7: kinematics (`python tools/robot_scheme.py robot/RTC-7-layout.txt`)

Zero configuration = the arm stretched as on the scheme. World frame: origin on the J1 axis at the
mounting face of the slewing bearing, +Z along J1 toward the arm, +X toward the lateral offsets.

## Joint axes (zero configuration)

| Joint | Drive | Point on the axis, mm | Direction | Motor side | Relation to the previous axis |
|---|---|---|---|---|---|
| J1 | SHM-150m | 0, 0, 0 | 0, 0, 1 | -Z |  |
| J2 | SHM-1000 | 0, 0, 121 | 1, 0, 0 | -X | intersect, 90 deg |
| J3 | SHM-500 | 105, 0, 121 | 0, 0, 1 | -Z | intersect, 90 deg |
| J4 | SHM-500 | 105, 0, 1451 | 1, 0, 0 | +X | intersect, 90 deg |
| J5 | SHM-150 | -168, 0, 1451 | 0, 0, 1 | -Z | intersect, 90 deg |
| J6 | SHM-150 | -168, 0, 2601 | 1, 0, 0 | -X | intersect, 90 deg |
| J7 | SHM-60 | 47.5, 0, 2601 | 0, 0, 1 | -Z | intersect, 90 deg |

Flange: 47.5, 0, 2762

## Standard DH (Spong): A_i = Rz(theta_i) Tz(d_i) Tx(a_i) Rx(alpha_i), theta_i = q_i + offset_i

| i | offset theta, deg | d, mm | a, mm | alpha, deg |
|---|---|---|---|---|
| 1 (J1) | 90.0 | 121.0 | 0.0 | 90.0 |
| 2 (J2) | 0.0 | 105.0 | 0.0 | -90.0 |
| 3 (J3) | 0.0 | 1330.0 | 0.0 | 90.0 |
| 4 (J4) | 0.0 | -273.0 | 0.0 | -90.0 |
| 5 (J5) | 0.0 | 1150.0 | 0.0 | 90.0 |
| 6 (J6) | 0.0 | 215.5 | 0.0 | -90.0 |
| 7 (J7) | -90.0 | 161.0 | 0.0 | 0.0 |

Row 7 ends in the tool frame on the flange (x = world X at zero). Base frame of the DH chain = world frame (identity).

Check: DH chain vs exact axis model on 200 random poses - max difference 1.4e-12 (mm / -).

## Geometry

- shoulder (J2 x J1) at z = 121; flange at zero pose 48, 0, 2762
- J2 -> J6 (shoulder -> wrist pitch) along the arm: 2486 mm
- reach from the shoulder axis to the flange: 2641 mm (with the assumed flange)
- consecutive axes all intersect: the lateral offsets lie along the pitch axes (out of the bending plane)
