# RTC-7: joint torques along the demo program, with accelerations (`python tools/robot_dynamics.py --speed 1`)

Inverse dynamics (Pinocchio RNEA) on `sim/RTC-7/RTC-7.urdf` (payload as exported, interface 4 kg), program `robot/RTC-7-demo.txt` at speed x1 (137.4 s). Gravity + inertia + Coriolis of the links; NOT included: rotor inertia of the motors through the reducers, friction, cables.

| Joint | Drive | Max gravity only, N·m | Max with dynamics, N·m | at t, s | Max speed, °/s | Max accel., °/s² | Rated (T_design) / start-stop, N·m | Peak, % of start-stop |
|---|---|---|---|---|---|---|---|---|
| J1 | SHM-150m | 0 | 16 | 17.7 | 20 | 13 | 103 / 155 | 10 % |
| J2 | SHM-1000 | 1060 | 1072 | 126.9 | 15 | 17 | 1000 / 1960 | 55 % |
| J3 | SHM-500 | 158 | 156 | 96.1 | 15 | 4 | 375 / 675 | 23 % |
| J4 | SHM-500 | 323 | 326 | 126.9 | 15 | 14 | 375 / 675 | 48 % |
| J5 | SHM-150 | 45 | 45 | 78.4 | 15 | 6 | 103 / 155 | 29 % |
| J6 | SHM-150 | 32 | 32 | 126.9 | 15 | 27 | 103 / 155 | 21 % |
| J7 | SHM-60 | 0 | 0 | 61.0 | 23 | 9 | 62 / 93 | 0 % |

Start-stop torque is the catalog limit for acceleration / braking; the rated torque - for the average load over a cycle.
