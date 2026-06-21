# Detector

*One detector gantry serving both endstations. Design-phase; values are TDR design targets.*

TomoWISE has a single detector system on a gantry that travels the experiment hutch on 7 m floor rails, from the microtomography station at 45 m to the hutch wall at 52 m. It serves both endstations, so it is modelled once, in the detection stage of the [descriptor](../inventory.md).

## Gantry

| Component | Family | Key specs (TDR target) | Notes |
| --- | --- | --- | --- |
| Detector gantry | `Table` | three axes Xd, Yd, Zd, with Zd on the 7 m floor rails | removable flight tube (1 mbar) reduces air scatter for the long propagation distances |

## Microscopes

Interchangeable visible-light microscopes couple the scintillator image to the cameras. The optics vendor is a design decision deferred to project year 2 (DET-2); the Optique Peter MICRX080 is the reference.

| Microscope | Family | Key specs (TDR target) | Status |
| --- | --- | --- | --- |
| MicLFOV | `Microscope` | large field of view, 1-2x magnification, NA > 0.2 | Family not yet in catalog |
| MicHR | `Microscope` | high resolution, 4x / 10x / 20x, NA > 0.4 | Family not yet in catalog |

## Cameras

Four cameras span the throughput-versus-speed-versus-resolution trade. The models are chosen in project year 2 (DET-1); the sensors below are the design targets.

| Camera | Family | Sensor / speed (design target) | Use |
| --- | --- | --- | --- |
| Camera I | `Camera` | 16-25 Mpix, 16-bit sCMOS, 100-150 fps | general throughput |
| Camera II | `Camera` | 4 Mpix, 12-bit CMOS, > 50,000 fps | high-speed dynamics |
| Camera III | `Camera` | ~4 Mpix, > 2,000 fps | streaming |
| Camera IV | `Camera` | 150 Mpix, 54 x 40 mm sensor, 3.76 um pixel | matches the large-sensor device already procured for DanMAX |

The camera models, the microscope vendor, and the trigger path are the main detector-side [open questions](../questions.md). See [Inventory](../inventory.md) for the Asset tree.
