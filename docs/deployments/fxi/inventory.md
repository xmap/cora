# Inventory

*The CORA Asset model for FXI: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/fxi/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/fxi-profile-collection`). No vendor Model is bound: part numbers are not in the profile collection, so they are carried as open questions, not bindings. Three TXM diffractive optics (`Condenser`, `ZonePlate`, `PhaseRing`) are catalog Families (graduated with this deployment); `BetrandLens` stays a loose family name that renders as text (FXI is its only sighting).

## The Asset tree

Root Asset `FXI` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | PV (verified) | What it is |
| --- | --- | --- | --- | --- |
| `FXI` | `Unit` | (root) | `XF:18ID*` | bound to the NSLS-II Site |
| `Source` | `Device` | InsertionDevice | (none) | 18-ID insertion device, identity-only |
| `Monochromator` | `Device` | Monochromator | `XF:18IDA-OP{Mono:DCM` | double-crystal mono; `-Ax:En` is the master energy |
| `CollimatingMirror` | `Device` | Mirror | `XF:18IDA-OP{Mir:CM` | first mirror (`cm`), piezo bender + load cell |
| `ToroidalMirror` | `Device` | Mirror | `XF:18IDA-OP{Mir:TM` | second mirror (`tm`) |
| `WhiteBeamSlit` | `Device` | Slit | `XF:18IDA-OP{PBSL:1` | white-beam-defining slit |
| `SecondarySourceSlit` | `Device` | Slit | (none) | secondary-source aperture (`TXM_SSA`) |
| `Filter` | `Device` | Filter | `XF:18IDB-ES{IOLOGIK5:E1211}:DO{1..8}-Cmd` | eight pneumatic foils on ioLogik relays |
| `XEng` | `Device` | PseudoAxis | `XF:18IDA-OP{Mono:DCM-Ax:En}Mtr` | master energy computed axis |
| `WhiteFluxMonitor` / `PinkFluxMonitor` / `MonoFluxMonitor` | `Device` | GenericProbe | `XF:18IDA-BI{WPFS:1}` / `{PMFS:1}` / `{MFS:1}` | Manta flux/position diagnostics |
| `SampleStage` | `Device` | LinearStage | `XF:18IDB-OP{Env:1-Ax:Xl/Yl/Zl}` | sample translation (sx/sy/sz) |
| `SampleRotary` | `Device` | RotaryStage | `XF:18IDB-OP{TXM:2-Ax:R}Mtr` | tomography theta (`pi_r`), PSO-triggered |
| `Condenser` | `Device` | Condenser | `XF:18IDB-OP{CLens:1-Ax:*}` | condenser optic (`clens`) |
| `Aperture` | `Device` | Aperture | `XF:18IDB-OP{Aper:1-Ax:*}` | TXM aperture (`aper`) |
| `ZonePlate` | `Device` | ZonePlate | `XF:18IDB-OP{ZP:1-Ax:*}` | zone-plate objective (`zp`) |
| `PhaseRing` | `Device` | PhaseRing | `XF:18IDB-OP{PR:1-Ax:*}` | Zernike phase ring |
| `BetrandLens` | `Device` | BetrandLens | `XF:18IDB-OP{BLens:1-Ax:*}` | Bertrand lens (`betr`), loose family |
| `IonChamber` | `Device` | GenericProbe | `XF:18IDB-BI{` | ion chambers ic1..ic4 (i404) |
| `Scintillator` | `Device` | Scintillator | `XF:18IDB-OP{Det:Lens` | scintillator-relay lens stage |
| `DetectorSupport` | `Device` | LinearStage | (none) | DetU/DetD rails; `DetU.z` is the propagation distance |
| `Camera` | `Device` | Camera | `XF:18ID1-ES{Kinetix-Det:1}` | imaging detector (live Kinetix) |
| `Magnification` | `Device` | PseudoAxis | (computed) | `(DetU.z / zp.z - 1) * 10` |
| `Zebra` | `Device` | TimingController | `XF:18ID-ES:1{Dev:Zebra1}:` | position-capture trigger box |

`Condenser`, `ZonePlate`, and `PhaseRing` graduated into the catalog with this deployment (a second deployment after 32-ID); `BetrandLens` stays loose, FXI-only, tracked as (OPTIC-3). All other families reuse the catalog.

## Computed axes

| Axis | Derivation | Notes |
| --- | --- | --- |
| `XEng` | the DCM energy record `-Ax:En` | master energy; driving it triggers the coupled `move_zp_ccd_xh` move (DCM, zone plate, condenser, aperture, detector co-move to hold magnification over 5 to 15 keV) |
| `Magnification` | `(DetU.z / zp.z - 1) * VLM`, `VLM = 10` | derived from two real Z positions; no PV |

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the FXI team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Insertion-device type (undulator vs wiggler) and parameters | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Device z positions (layout reference) | all devices | `unknown-pending-confirmation` | (LAYOUT-1) |
| DCM crystal cut and energy range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Zone-plate values (NanoTools, 244 um, 30 nm are code constants) | `ZonePlate` | `unknown-pending-confirmation` | (OPTIC-4) |
| Filter foil materials and thicknesses | `Filter` | `unknown-pending-confirmation` | (FILT-1) |
| Sample stage vendor and travel | `SampleStage` | `unknown-pending-confirmation` | (STAGE-1) |
| Rotary hardware, encoder resolution, max speed | `SampleRotary` | `unknown-pending-confirmation` | (STAGE-2) |
| Scintillator material and thickness | `Scintillator` | `unknown-pending-confirmation` | (DET-1) |
| Detector-support PV prefix | `DetectorSupport` | `unknown-pending-confirmation` | (DET-2) |
| Camera roster (which installed/active; second position?) | `Camera` | `unknown-pending-confirmation` | (CAM-1) |
| Camera vendor part numbers | `Camera` | `unknown-pending-confirmation` | (CAM-2) |
| Ion-chamber channel PV suffixes | `IonChamber` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller boxes (model/protocol/serial/firmware/IP) | both controllers | `unknown-pending-confirmation` | (DRIVE-1) |
