# Techniques

*What the modelled part of 8-ID is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 8-ID's signature technique, **XPCS, is now a catalog Method** (`cora.capability.xpcs`): it is the second beamline after LCLS-MFX to need a DAQ-owned high-rate frame stream, which graduated XPCS out of the imaging-heritage catalog. Small-angle scattering and six-circle diffraction stay pending until they enter scope (`TECH-1`).

## X-ray photon correlation spectroscopy

XPCS measures the time correlations of a coherent speckle pattern to probe sample dynamics, so it records long, fast time series on an area detector under a precisely gated exposure.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| XPCS | [`xpcs`](../../catalog/methods.md) | coherent-scattering intensity time series on the Eiger / Lambda / Rigaku detectors, gated by the softGlue timing; now a catalog Method. Its acquisition is a DAQ-owned high-rate frame stream with no executing body yet, the [event-stream acquisition axis](model.md#deliberately-not-here-yet) (Stage 1) |
| Small-angle scattering | `small_angle_scattering` | static SAXS on the same detectors; a Plan setting over the same chain |

Both need the [XPCS sample stage](equipment/sample.md), the [coherent detectors](equipment/detector.md), and the flight path. The fast shutter and softGlue timing (`XPCS-1`, `XPCS-3`) gate the exposure.

## Six-circle diffraction

The 8-ID-E Huber diffractometer orients a single crystal through six circles and scans reciprocal space, sharing the diffraction Method with 4-ID.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Six-circle diffraction | `diffraction` | reciprocal-space scans on the six-circle Huber; shares the 4-ID `diffraction` Method (`TECH-1`) |

It needs the [diffractometer](equipment/sample.md). The reciprocal-space coordination is `DIFF-2`; the reusable `Assembly(Diffractometer)` is on [Model](model.md#deliberately-not-here-yet).

## Not modelled yet

The XPCS Method now exists, but the concrete acquisition primitive that executes it (a DAQ-owned high-rate frame stream, not a poll-to-Done capture) does not: that is the [event-stream acquisition axis](model.md#deliberately-not-here-yet), now at Stage 1 (8-ID XPCS is its second beamline after LCLS-MFX). Small-angle scattering and diffraction Methods remain an owner-scope decision (`TECH-1`); see [Open questions](questions.md) for the world-facts to confirm first.
