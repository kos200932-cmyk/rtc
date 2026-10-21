# RTC-7: joint loads of the model vs the requirements (`python tools/joint_compare.py`)

Requirements: `robot/RTC-7-joint-requirements.txt` (customer table 2). Model: `sim/RTC-7/RTC-7.urdf`, inverse dynamics (Pinocchio). Forces and tilting moment - the wrench passed by the joint, at the centre of its output face. Cases: **S** statics, worst of 20000 random poses; **P** demo program retimed to n0 (`robot/RTC-7-demo-n0.txt`, `sim/RTC-7/RTC-7-n0-traj.csv`); **A t** start / stop of the joint alone to n0 in t s, worst pose (n0 / t constant acceleration at speed n0). Not included: motor rotor inertia, friction, cables.

## Torque about the axis, N·m

| Joint | Size | Required | S | P | A 0.5 | A 0.2 | Max / required |
|---|---|---|---|---|---|---|---|
| J1 | ШМ-150м | 150 | 0 | 16 | 162 | 405 | 270 % |
| J2 | ШМ-1000 | 1000 | 1068 | 1072 | 1187 | 1365 | 136 % |
| J3 | ШМ-500 | 500 | 353 | 156 | 357 | 392 | 78 % |
| J4 | ШМ-500 | 500 | 325 | 326 | 345 | 378 | 76 % |
| J5 | ШМ-150 | 150 | 52 | 45 | 52 | 54 | 36 % |
| J6 | ШМ-150 | 150 | 32 | 32 | 32 | 33 | 22 % |
| J7 | ШМ-60 | 60 | 0 | 0 | 0 | 0 | 0 % |

## Tilting moment, N·m

| Joint | Size | Required | S | P | A 0.5 | A 0.2 | Max / required |
|---|---|---|---|---|---|---|---|
| J1 | ШМ-150м | 1520 | 1081 | 1072 | 1083 | 1085 | 71 % |
| J2 | ШМ-1000 | 590 | 428 | 382 | 442 | 485 | 82 % |
| J3 | ШМ-500 | 1300 | 917 | 917 | 924 | 941 | 72 % |
| J4 | ШМ-500 | 550 | 327 | 162 | 328 | 328 | 60 % |
| J5 | ШМ-150 | 480 | 277 | 277 | 277 | 280 | 58 % |
| J6 | ШМ-150 | 170 | 33 | 29 | 33 | 33 | 19 % |
| J7 | ШМ-60 | 60 | 9 | 9 | 9 | 9 | 15 % |

## Radial force, N

| Joint | Size | Required | S | P | A 0.5 | A 0.2 | Max / required |
|---|---|---|---|---|---|---|---|
| J1 | ШМ-150м | 40 | 0 | 13 | 78 | 192 | 481 % |
| J2 | ШМ-1000 | 890 | 762 | 784 | 819 | 904 | 102 % |
| J3 | ШМ-500 | 740 | 603 | 606 | 621 | 648 | 88 % |
| J4 | ШМ-500 | 525 | 367 | 385 | 384 | 410 | 78 % |
| J5 | ШМ-150 | 390 | 275 | 278 | 278 | 282 | 72 % |
| J6 | ШМ-150 | 270 | 170 | 180 | 171 | 174 | 67 % |
| J7 | ШМ-60 | 190 | 124 | 126 | 124 | 124 | 66 % |

## Axial force, N

| Joint | Size | Required | S | P | A 0.5 | A 0.2 | Max / required |
|---|---|---|---|---|---|---|---|
| J1 | ШМ-150м | 1135 | 1017 | 1039 | 1017 | 1017 | 92 % |
| J2 | ШМ-1000 | 33 | 0 | 13 | 0 | 0 | 39 % |
| J3 | ШМ-500 | 730 | 603 | 603 | 603 | 603 | 83 % |
| J4 | ШМ-500 | 520 | 367 | 183 | 367 | 367 | 71 % |
| J5 | ШМ-150 | 390 | 275 | 275 | 275 | 275 | 71 % |
| J6 | ШМ-150 | 270 | 170 | 127 | 170 | 170 | 63 % |
| J7 | ШМ-60 | 190 | 124 | 132 | 124 | 124 | 70 % |

## Speed and power

| Joint | n0, °/s | P_nom, W | P: max speed, °/s | P: max power, W | A 0.5: torque x n0, W | A 0.2: torque x n0, W | S: torque x n0, W |
|---|---|---|---|---|---|---|---|
| J1 | 20 | 50 | 20 | 3 | 57 | 141 | 0 |
| J2 | 15 | 260 | 15 | 218 | 311 | 357 | 280 |
| J3 | 15 | 130 | 15 | 37 | 94 | 103 | 92 |
| J4 | 15 | 130 | 15 | 80 | 90 | 99 | 85 |
| J5 | 15 | 40 | 15 | 11 | 14 | 14 | 13 |
| J6 | 15 | 40 | 15 | 5 | 8 | 9 | 8 |
| J7 | 30 | 30 | 23 | 0 | 0 | 0 | 0 |
