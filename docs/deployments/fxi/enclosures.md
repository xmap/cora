# Enclosures

*The two access-gated hutches and their permits. Reverse-engineered; the PSS search-and-secure permit leaves are not in the profile collection (PSS-1).*

FXI occupies two enclosures, partitioned by the EPICS PV branch letter: `XF:18IDA-*` is the optics hutch, `XF:18IDB-*` the experiment hutch. Each is an access-gated volume within the NSLS-II Site whose personnel-safety permit gates beam-on work.

## 18-IDA (optics hutch)

Holds the source-conditioning optics: the double-crystal monochromator, the two mirrors, the white-beam slit, the filters, and the flux monitors.

- Permit: the only permit handle exposed in source is the PPS photon-shutter status `XF:18IDA-PPS{PSh}Pos-Sts` (and `Sts:Cls-Sts`). This is the shutter state, not the search-and-secure permit leaf, which is unknown (PSS-1).
- Note: in source the shutter-status signals are writable `EpicsSignal` objects; CORA's read-only treatment of them is design discipline, not enforced by the device type.

## 18-IDB (experiment hutch)

Holds the sample stage, the transmission-microscopy optics, and the detector.

- Permit: the PSS permit leaf is unknown (PSS-1).
- Open boundary: the Photometrics Kinetix camera lives in a `XF:18ID1-ES` namespace, distinct from `XF:18IDB-*`. Whether `18ID1-ES` is a separate endstation area or part of 18-IDB is unresolved (ENC-1); CORA folds it into 18-IDB for now.

Clearances, the facility safety forms that must be Active to start, are issued at the [NSLS-II Site](../nsls2/index.md#the-safety-envelope) (`NSLS-II personal safety system`, pending).
