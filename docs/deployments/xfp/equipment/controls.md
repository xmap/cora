# Controls

*The control stack, the dose-delivery timing, the sample-custody seam, and the offline-readout seam. First cut; handles read from the profile collection, carried confirm.*

XFP runs on the NSLS-II EPICS / ophyd control stack, the same floor as the rest of the NSLS-II fleet, with a handful of PV-bound fluidic actuators on top. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky profile collection ([NSLS2/xfp-profile-collection](https://github.com/NSLS2/xfp-profile-collection), the `startup/` files), so the descriptor carries the real PV roots. The optics zone carries the bendable mirror (`XF:17BM-OP{Mir:1}`, `OPT-1`) and the slits (`FE:C17B-OP{Slt:1}`, `XF:17BMA-OP{Slt:ADC}`, `OPT-2`); the dose gating carries the shutters (`XF:17BMA-EPS{Sh:1}`, `XF:17BM-PPS{Sh:FE}`) and the delay-generator dose timer (`XF:17BMA-ES:2{DG:1}`, `DOSE-1`); the endstation carries the sample stages (`XF:17BMA-ES:1{Stg:5}`, `XF:17BMA-ES:2{Stg:7}`), the delivery pump (`XF:17BMA-ES:1{Pmp:02}`, `FLOW-1`), and the flux monitors (`XF:17BM-BI{EM:1}`, `DET-1`). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## The dose-delivery timing

The dose is the experiment, so its timing is worth spelling out. There are three ways a dose is delivered, and CORA conducts each over the `ControlPort`:

| Dose mode | How the exposure is timed | Devices conducted |
| --- | --- | --- |
| Seconds-scale | software-timed: open the pre-shutter, wait the exposure time, close it | `DoseShutter` (Shutter), `FluxMonitor` |
| Millisecond | the DG535 delay generator sets an opening-time and fires the Uniblitz fast shutter once | `DoseTimer` (TimingController), the Uniblitz (a PV-less shutter downstream of the timer), `FluxMonitor` |
| Shutterless high-throughput | the HTFly stage sweeps through the defining slit at a set velocity; exposure = slit gap / velocity | `HtFlyStage` (LinearStage), `DefiningSlit` (Slit), `FluxMonitor` |

In every mode the `FilterWheel` sets the dose rate and the `FluxMonitor` records the flux time-series; the delivered dose is exposure time times flux times attenuation. The dose timer (`DoseTimer`) binds `TimingController` because its anatomy is a settable opening-time plus a single-shot trigger, the same timing-box role the fleet's other position-capture / trigger boxes fill; the Uniblitz it fires has no EPICS PV of its own and is modelled downstream of the timer (`DOSE-1`).

## The sample-custody and offline-readout seam

XFP's run produces a footprinted sample and a dose record, and the structural readout is offline. Three pieces sit in the seam rather than the device tree:

- **The fraction collector** (`XF:17BM-ES:1{FC:1}`) is a PV-bound aliquot-routing actuator (a collect / waste valve, a tube index, a fill pattern, home). No existing Family fits an aliquot-router cleanly, and at n=1 CORA does not coin a `FractionCollector` Family; it is carried in the sample-custody seam, the hand-off that captures footprinted aliquots into tubes for offline analysis (`FC-1`, `READOUT-1`).
- **The 96-well plate** is addressed in pure Python (8 columns x 12 rows, a coordinate table, no robot and no PV); moving to a well is a move on the `HighThroughputStage`. It is a Procedure over the spine plus a Subject custody thread, the i03 / MX3 / LIX custody-as-Procedure precedent, here at the no-robot end of that spectrum (`HT-1`).
- **The offline mass-spectrometry readout** is downstream, off the beamline, and absent from the profile collection. CORA keeps the dose record as the system of record for a footprinting run; the MS structural analysis is a separate, later step (`READOUT-1`).

## The orchestration seam

The XFP acquisition runs through bluesky plans (gate a timed dose, or sweep the HTFly stage, while the pump flows the sample and the QuadEM records the flux trace), publishing documents to Kafka with run metadata in Redis; there is no Tiled and no queue-server in the profile collection (`CTRL-1`). That orchestration is the seam CORA's edge replaces: CORA conducts the dose program over the `ControlPort`, driving through ophyd / EPICS and the fluidic actuators rather than replacing them. The temperature / bias diagnostics (an SR630 thermocouple monitor, the Sydor bias controller) are read-only alignment-flux proxies, deferred (`TEMP-1`).

## Equipment protection

Only the front-end photon-shutter enable status (`XF:17BM-PPS{Sh:FE}` enabled-status, interlock-derived) is in the profile collection; plans refuse to open it when disabled. The rest of the PSS search-and-secure permit signals are absent and not invented here (`PSS-1`). Because the experiment is high-flux white-beam irradiation of biological samples, the dose itself is a hazard the safety tier would gate; that mapping is not modelled in this cut and is carried against the safety questions (`PSS-1`, `DOSE-1`).
