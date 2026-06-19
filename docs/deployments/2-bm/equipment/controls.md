# Controls

*How 2-BM hardware is driven: the controllers and drive crates, and the trigger wiring that links them. A consolidated view; the per-controller detail lives in the Assets inventory.*

A controller is an `Asset` like any other, but it relates to the hardware it moves sideways, through the `controller_id` back-reference, not through containment. That is why controls is its own area rather than a part of any one station: a single controller routinely spans the beam-path stations.

## The controller graph

- `FrontEndDrive` (an OMS VME58 crate in the optics hutch) drives the front-end optics: the mirror, monochromator, conditioning slits, filter, and the `2-BM-B` sample slits.
- `SampleStageDrive` (a second OMS VME58 crate) drives the sample stages, and also the Detector's objective and camera selectors.
- `Timing` (a softGlueZynq FPGA box) generates the trigger pulse train: one leg starts each camera exposure, two more step the sample piezo on a readout boundary.
- The Aerotech drives (`RotaryDrive`, `HexapodDrive`, `PropagationDistanceDrive`) each drive one precision stage.
- The Jena piezo controllers (`OpticsFineDrive`, `SampleFineDrive`) drive the fine-positioning piezo axes.

`SampleStageDrive` reaching the Detector selectors, and `Timing` reaching both the camera and the sample piezo, are the clearest cases: nesting controls under a single station would mis-attribute most of the graph.

## Where the detail lives

The full controller back-reference table (which crate drives which Assets, the bound vendor Model, the EPICS handle) and the trigger-wiring port maps are on the [Assets](../inventory.md) page, the source of truth until this view graduates to carry them. Family-level affordances for `MotionController` and `TimingController` are on the same page.
