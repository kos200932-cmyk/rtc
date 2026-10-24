# "Юла" (J1 output -> ОПУ inner ring -> link 1), 30ХГСА - quick FEA + joints, 2026-10-23

Model links-user/YULA/YULA.txt (rebuilt as a body of revolution from the IGES body: volume +0.5 %, chamfers 1x45
not modelled), 1.81 kg. CalculiX tet10 h 2.5, E 210 GPa. Assembly frame: X = J1 axis.

| Case | support | load | vM peak / away, MPa | n = 835 / peak | rotation, mrad |
|---|---|---|---|---|---|
| arm tilting 1239 N·m + axial -1277 N (ОПУ loads, robot/RTC-7-loads-v2) | flange on the ОПУ inner ring (x=28) | link base face x=36 + bore D115 | 5.5 / 0.6 | >100 | 0.002 |
| J1 torque 135 N·m (KB25 momentary max) | lip on the KB25 output (x=26) | flange faces x=28 and x=36 | 6.9 / 1.8 | >100 | 0.003 |

Bolts (hand check): 12 x M8 on D139 (link base <- flange <- ОПУ ring): tilting 1239 N·m -> max 3.0 kN per bolt
(conservative, neutral axis on the centre) vs preload ~17 kN (10.9) - no gap; J1 torque 135 N·m -> 0.16 kN shear per
bolt vs friction ~2.5 kN. 16 x M4 on D77 (into the KB25 output): 135 N·m -> 0.22 kN per bolt vs friction ~0.6 kN (n 2.7).
Open point: the adapter ties the KB25 output to the ОПУ inner ring rigidly - the tilting moment is shared by the ОПУ
and the KB25 output bearing (KB25 M_tilt 193.5 N·m) by their stiffnesses + any misalignment of the two axes.

## J1 housing held only against turning (user, 2026-10-24): J1 hangs on its output on the ОПУ -> the KB25 output
bearing no longer shares the arm tilting moment. Yula carries: J1 torque (135 N·m peak) + J1 weight + the bolt stack.
Lighter variant links-user/YULA/variants/YULA-light.txt: upper tube D115 shortened 18 -> 10 (spigot in the link
base), bore above the lip D88 -> D100: 1.35 kg (was 1.81); J1 torque 135 N·m + weight: vM 8.2 / 2.5 MPa; stack
1239 N·m: 5.6 MPa. Heights unchanged (flange x 28..36 is the spacer between the ОПУ ring and the link base).
