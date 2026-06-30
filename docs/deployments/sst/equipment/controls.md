# Controls

*The fast-shutter-gated acquisition, the branch selection, the motion controllers, and the seam between CORA and the floor.*

## Triggering and branch selection

SST does not use a hardware position-capture box. Its detectors run in software-triggered modes, gated by the endstation fast shutter (`FastShutter`, `XF:07ID2-ES1{FSh-Ax:1}` with a diode-control line); a measurement is a held exposure on the active endstation's detector. Because SST has two branches sharing one sector, the endstation in control (`XF:07ID1-CT{Bl-Ctrl}Endstn-Sel`) selects which branch and endstation are live; CORA would model that selection as part of conducting a Run, not as a device Asset.

## Motion controllers

The manipulators, mirrors, and detector stages across both branches are driven by endstation and optics motion controllers whose box models, firmware, and IPs are not fully in the profile collection (DRIVE-1), so `EndstationMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the SST floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the acquisition: selecting the branch and endstation, positioning the sample (including the photoemission and grazing geometries), setting the energy, and collecting the active detector under the gated exposure;
- the choice of technique, branch, detector, and in-situ environment program, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction (here over the TOML-declared device layer): the `ControlPort` boundary;
- the two coupled energy pseudopositioners (EPU60 + PGM soft, U42 + DCM tender), the mirror benders, the UHV vacuum automation, the PSS interlock, and the endstation detector IOCs;
- the facility filestore where the per-run data lands. CORA moves it, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to SST, working over the ports: acquisition over the `ControlPort`, the per-technique reduction (scattering reduction, photoemission spectra, NEXAFS spectra) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset.

The software IOCs (`Greateyes`, `SES`, `TES`, `Lakeshore`, `SR570`, `I400`, the flood gun, the source-measure unit, the syringe pump) are referenced by PV namespace only, never registered as Assets.
