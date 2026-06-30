# Detector

*The detectors. PVs verified against dodal `src/dodal/beamlines/p51.py` and `devices/xspress3/xspress3.py`. The EDE primary detector is an open question.*

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `BL51P-EA-DET-03:` | Xspress3 fluorescence (16-channel) |

## The strip detector: the EDE primary, absent from source

What makes EDE energy-dispersive is its detector: a **position-sensitive strip detector** sits where the polychromator's energy fan lands, so each strip reads a different energy and the whole absorption spectrum is captured in one exposure, no scan. That detector (for example an XH or germanium microstrip) is **not in the dodal commissioning module**. CORA does not fabricate it: it is named as the open question STRIP-1, with the modelling choice it raises (does a 1D energy-dispersed strip fit `Camera`, or is it a new detector class?) left for when it is PV-bound.

## What is modelled: the fluorescence Xspress3

The one detector in the module is the `FluorescenceSpectrometer`, an Xspress3 16-channel energy-dispersive detector (`BL51P-EA-DET-03:`), which reuses the graduated `EnergyDispersiveSpectrometer` family (#345). It is the secondary, fluorescence-mode detector (fluorescence-yield EXAFS), not the dispersive primary. The dodal module currently constructs it with `skip=True` (defined but not loaded by default), so CORA carries it `confirm` and tracks its live status, and the absent I0 / It ion-chamber flux chain, as DET-1.
