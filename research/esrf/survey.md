# ESRF research brief

Staging notes, not published docs. These files capture what CORA can learn about ESRF beamlines
from their public controls configurations. They are inputs to later modeling decisions, not
deployment documentation. Promote confirmed facts into descriptors
(`deployments/<id>/beamline.yaml`, `catalog/catalog.yaml`) or the published
`docs/deployments/<id>/` pages when a decision lands.

Extractions to date:

- `beamlines/id19/` -- ID19, the long microtomography beamline (the first ESRF deployment).
- `beamlines/id16b/` -- ID16B, the nano-analysis / nano-imaging beamline (nano-tomography +
  nano-XRF), the second ESRF deployment and the fleet's first nanoprobe on a BLISS floor.
- `beamlines/id28/` -- ID28, momentum-resolved inelastic X-ray scattering (IXS), a shipped
  deployment given a retrospective Tier-2 device pass; the multi-analyzer crystal arm is the
  loose-family disambiguation case (EnergyAnalyzer vs SpectrometerArm, see its facts.md).
- `beamlines/id32/` -- ID32, soft X-ray RIXS / XMCD / XES, a shipped deployment given a
  retrospective Tier-2 device pass; the RIXS and XES grating arms reinforce the loose
  SpectrometerArm (RIXS-1, grating lineage), the other half of the disambiguation against ID28.
- `beamlines/id06/` -- ID06, hard X-ray / dark-field microscopy (DFXM) + X-ray optics testing +
  large-volume press (LVP); NOT yet a deployment, a net-new device pass. The headline LVP
  technique has NO press device in the public config (only generic stages + a view camera),
  recorded as the open question PRESS-1, not invented.
- `beamlines/bm26/` -- BM26 (DUBBLE), the Dutch-Belgian CRG bending-magnet beamline (SAXS / WAXS
  + XAFS); NOT yet a deployment, a net-new device pass. First bending-magnet beamline in the ESRF
  set (no insertion device); the CRG partner-operated model is a Federation / Trust seam note.
- `beamlines/bm25/` -- BM25 (SpLine), the Spanish CRG bending-magnet beamline (XRD / XAS); NOT yet
  a deployment. Its public config is a PARTIAL mirror (detectors + sample environment only; no
  optics, motion, slits, shutters, or source), so the absent halves are recorded as open
  questions (CONFIG-1 / MONO-1 / MOTION-1), not inferred.
- `beamlines/bm23/` -- BM23, the bending-magnet XAS beamline (EXAFS / XANES + XES on a Si555 Johann
  crystal-analyzer spectrometer); NOT yet a deployment. Its config is STALE (2022 snapshot, STALE-1)
  and carries cross-beamline leftovers (BM05/BM29/ID10/ID24 devices, XBL-1) that are excluded;
  reinforces the graduated EmissionSpectrometer family.
- `recurrence.md` -- the cross-ESRF Family-frequency fold; COMPLETE public-config set (ID19 / ID16B /
  ID28 / ID32 / ID06 / BM26 / BM25 / BM23, all eight). Standing verdict: ESRF earns no new catalog Family.

ESRF beamlines that publish a Beacon config (`<beamline>/beamline_configuration`, public on
gitlab.esrf.fr) are the modellable set. As of 2026-06 the public ones are: ID06, ID16B, ID19,
ID28, ID32, BM23, BM25, BM26. ID16B (nano-imaging) and ID32 (soft X-ray RIXS / XMCD) and ID28
(IXS) are the strongest next picks after ID19.

## The source: ID19's public BLISS Beacon config

ESRF runs BLISS (a Tango-based control system), not EPICS, and the prior assumption that ESRF
per-beamline configs are not published the way Diamond publishes `dodal` was wrong. ID19's live
Beacon device database is a **public** git project:

- `gitlab.esrf.fr/id19/beamline_configuration` (visibility: public; cloned at commit `b78389a`,
  last activity 2026-03-31). This is the actual `/users/blissadm/local/beamline_configuration`
  YAML device database the beamline runs on, ~200 YAML files: motors, detectors, mono, slits,
  attenuators, shutters, insertion devices, and per-endstation BLISS sessions.

So ID19 is reverse-engineered the same way the dodal beamlines are: real device names and real
control handles read from the beamline's own controls source, every value carried `confirm`
until ID19 staff verify it (a config snapshot is strong evidence, not a CORA-owned fact). The
BLISS core repo (`gitlab.esrf.fr/bliss/bliss`) was also read, but only for the YAML grammar
(how a controller declares axes, how a Lima detector is addressed by a Tango name); the device
facts come from ID19's own config.

This corrects the first ID19 scaffold, which was built from the BLISS *demo* config plus ESRF
public pages because the real config had not yet been located. With the real config in hand,
the descriptor carries real handles, the source and optics are no longer deferred, and both the
micro-resolution (MR) and high-resolution (HR) tomography endstations are modelled.

## The standing verdict

The ID19 Beacon config is a strong reference for the BLISS / Tango floor and the device reality
that `beamline.yaml` points at, and a low-value template for CORA's spine. CORA intentionally
models an event-sourced governance and provenance spine (event store, Trust, Federation, Asset
lifecycle and condition, Capability and affordance contracts, portable Assemblies, Calibration
provenance, Decision and Agent provenance, the Run versus Procedure boundary) that the config
does not carry. Mine the config as data to learn from, never as a spec to mirror. For physical
facts defer to the config plus the external source plus the operator, never to CORA's own
internal consistency.

The point of ID19 is not a new device family (microtomography is plain `tomography` Method reuse,
the same the 2-BM pilot and MAX IV TomoWise carry; the rotation stages bind `RotaryStage`, the
positioning stages bind `LinearStage`, the detectors bind `Camera`, the optics bind existing
families). The point is the **control plane**: ID19 is CORA's first live, non-EPICS, BLISS / Tango
floor. Hold the device families constant, move one axis.

## What the config shows (and the first scaffold deferred or guessed)

- **Two-plus tomography endstations, not one.** The BLISS sessions are `MRTOMO` (micro-resolution),
  `HRTOMO` (high-resolution), `MHTOMO`, `MEDTOMO`, `LATOMO` (laminography), `RADIO`, `PCOTOMO`.
  This cut models MR and HR as the two main stations; the rest are noted, not modelled.
- **Real rotation stages.** `mrsrot` (Elmo, micro-res), `hrsrot` (Elmo_whistle, high-res, up to
  900 deg/s), plus `mhsrot`, `medsrot`. Sample positioning via IcePAP `iceid191/192` axes
  (`hrsx/hrsy/hrsz`, `mrsx/mrsy`) and `XYOnRotation` pseudo-axis controllers.
- **Real detectors.** Lima detectors `frelon1/2` (`id19/limaccd/frelon*`), `pco4k`, three PCO
  Dimax (`dimax_lid19det1..3`), `basler1/2`; FalconX and Mercury fluorescence MCAs.
- **Real source.** ESRF_Undulator axes `u13a_gap`, `u32a_gap`, `w150b_gap` + `w150b_taper`
  (wiggler), `u17_6c_gap`, `u32c_gap` (Tango `//acs.esrf.fr:10000/ID/MASTER/ID19`).
- **Real optics.** `TripleMono` (`Id19Mono`, Bragg 17-99 keV, Laue and multilayer modes),
  primary/secondary slits (`psu/psd/psf/psb`, `ssu/ssd/ssf/ssb`), white-beam transfocator
  (`ID19Transfocator`, 8 Be lenses), white-beam attenuators (`wba1/wba2`, `MultiplePositions`).
- **Real shutters.** `bsh1/bsh2` (`TangoShutter id19/bsh/{1,2}`), `frontend`
  (`//acs.esrf.fr:10000/fe/master/id19`).

## The extraction pass (manual)

There is no automated extractor for BLISS (`scripts/reverse_engineer/` reads the Guarneri
`devices.yml` + ophyd AST, which is EPICS-only). The procedure was:

1. Clone the public ID19 config (`git clone https://gitlab.esrf.fr/id19/beamline_configuration`).
2. Read `motors/`, `detectors/`, `mono/`, `slits/`, `attenuators/`, `transfocators/`,
   `shutters/`, `devices/insertion_devices.yml`, and `sessions/` to map the device tree and the
   per-endstation grouping.
3. Map the BLISS objects onto CORA Families at Asset granularity (the stage, not the per-axis
   tuning), carrying the BLISS object name / Tango handle in the descriptor `pv` field (the
   opaque control-handle slot) and every value `confirm`.

## What is here

- `beamlines/id19/facts.md`: the device inventory for ID19, read from the public config, mapped
  to CORA Families. Every row is `confirm`.

## Gaps neither source fills (CORA-native)

Event sourcing and system of record, Asset lifecycle and condition as data, Calibration provenance,
Decision and Agent provenance, the Run versus Procedure output-of-record boundary, Capability and
affordance contracts, cross-facility Federation and per-command authorization. Confirming their
absence from the BLISS config is itself part of the justification for the spine.
