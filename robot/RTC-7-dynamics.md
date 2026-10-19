# RTC-7: joint torques along the demo program, with accelerations (`python tools/robot_dynamics.py --speed 1`)

Inverse dynamics (Pinocchio RNEA) on `sim/RTC-7/RTC-7.urdf` (payload as exported, interface 4 kg), program `robot/RTC-7-demo.txt` at speed x1 (39.7 s). Gravity + inertia + Coriolis of the links; NOT included: rotor inertia of the motors through the reducers, friction, cables.

| Joint | Drive | Max gravity only, N·m | Max with dynamics, N·m | at t, s | Max speed, °/s | Max accel., °/s² | Rated (T_design) / start-stop, N·m | Peak, % of start-stop |
|---|---|---|---|---|---|---|---|---|
| J1 | SHM-150m | 0 | 106 | 30.8 | 59 | 52 | 103 / 155 | 68 % |
| J2 | SHM-1000 | 1059 | 1206 | 35.9 | 46 | 41 | 1000 / 1960 | 62 % |
| J3 | SHM-500 | 157 | 153 | 26.2 | 113 | 130 | 375 / 675 | 23 % |
| J4 | SHM-500 | 322 | 377 | 35.9 | 63 | 65 | 375 / 675 | 56 % |
| J5 | SHM-150 | 45 | 48 | 35.9 | 113 | 173 | 103 / 155 | 31 % |
| J6 | SHM-150 | 32 | 37 | 35.9 | 47 | 77 | 103 / 155 | 24 % |
| J7 | SHM-60 | 0 | 0 | 21.3 | 169 | 260 | 62 / 93 | 0 % |

Start-stop torque is the catalog limit for acceleration / braking; the rated torque - for the average load over a cycle.
