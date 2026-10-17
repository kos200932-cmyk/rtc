# Joint check (`python tools/joint_check.py`)

Assumed reducer efficiency eta = 0.8. Torques in N*m, speeds in rpm.
Required ratio = T_nom / (motor torque x eta); for an actuator the motor torque is already after its own gearbox.

Reducer T: catalog rated / start-stop / momentary max at the output.

| Joint | Reducer | Motor | T_nom | Reducer T rated / start-stop / max | Motor T rated / peak | Ratio needed: from peak / from rated | Reducer ratio | T_out rated / peak | n_out |
|---|---|---|---|---|---|---|---|---|---|
| SHM-60 | DMRD-KB25 | RI70-KV95 | 60 | 62 / 93 / 186 | 0.94 / 2.68 | 28.0 / 79.8 | ? | ? / ? | ? |
| SHM-150 | DMRD-KB32 | RI80-V2-KV75 | 150 | 103 / 155 / 310 | 1.45 / 4.10 | 45.7 / 129.3 | ? | ? / ? | ? |
| SHM-500 | DMRD-KB45 | RI115-PH-KV40 | 500 | 375 / 675 / 1350 | 5.50 / 16.00 | 39.1 / 113.6 | ? | ? / ? | ? |
| SHM-1000 | DMRD-80E | AK80-9-V3-KV100 | 1000 | ? / ? / ? | 9.00 / 22.00 | 56.8 / 138.9 | ? | ? / ? | ? |

## SHM-60

- links: OK
- to fill: DMRD-KB25: DATA ratio
- to fill: RI70-KV95: PORT stator
- to fill: RI70-KV95: PORT rotor
- to fill: sensor: component not chosen

## SHM-150

- links: OK
- to fill: DMRD-KB32: DATA ratio
- to fill: RI80-V2-KV75: PORT stator
- to fill: RI80-V2-KV75: PORT rotor
- to fill: sensor: component not chosen

## SHM-500

- links: OK
- to fill: DMRD-KB45: DATA ratio
- to fill: RI115-PH-KV40: PORT stator
- to fill: RI115-PH-KV40: PORT rotor
- to fill: sensor: component not chosen

## SHM-1000

- links: OK
- to fill: DMRD-80E: DATA OD
- to fill: DMRD-80E: DATA L
- to fill: DMRD-80E: DATA bore
- to fill: DMRD-80E: DATA ratio
- to fill: DMRD-80E: DATA T_rated
- to fill: DMRD-80E: DATA T_peak
- to fill: DMRD-80E: DATA mass
- to fill: DMRD-80E: PORT input
- to fill: DMRD-80E: PORT motor_side
- to fill: DMRD-80E: PORT base
- to fill: DMRD-80E: PORT output
- to fill: AK80-9-V3-KV100: PORT base
- to fill: AK80-9-V3-KV100: PORT output
- to fill: sensor: component not chosen
