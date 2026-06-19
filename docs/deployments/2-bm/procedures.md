# Procedures

*Operation BC Procedures registered at 2-BM.*

A Procedure is the record of one operational task. It acts on a set of target Assets and may realize a [Capability](../../catalog/capabilities.md); it runs either standalone or as a phase of a [Run](experiment.md). The Procedure aggregate does not itself bind a Method, Practice, or Plan: those name the technique and its wiring, while the Procedure is the task record and its per-step log. See [Model](../../architecture/model.md) for the aggregate shape.

The split between a Run and a Procedure is the lens, not the data product: a Run is the measurement batch (ISA-88), normally against a [Subject](experiment.md) and composed by a Campaign; a Procedure is an operational task (ISA-106). Both can produce a [Dataset](experiment.md) (a Dataset cites either a producing Run or a producing Procedure), so whether data comes out does not decide it. The dark- and flat-field baselines are subject-less calibration captures, kept with the [Runs](experiment.md); the tasks here are the operational ones.

An operation can also be authored as a [Recipe](recipes.md): a reusable, parameterized step sequence (setpoint / check / action) that expands into a Procedure once an operator binds its tunable values.

This page is organized by modeling status: the Procedures CORA [models today](#modeled-today), the [deferred](#deferred) ones still gated on staff facts or hardware. Two reference sections close it: the [beam-mode context](#beam-modes) the coordinated optic moves depend on, and the [staff procedures source](#from-the-2-bm-procedures-source) this page adopts from.

## Modeled today

The operational tasks CORA models now, grouped by kind: homing, alignment, characterization, recovery, and the coordinated energy change.

| Kind | Procedure | Target Assets |
| --- | --- | --- |
| Homing | `motor_homing` | `Rotary`, `SampleTop_X` |
| Alignment | `first_light` | `StationShutter` + image chain |
| Alignment | `resolution_alignment` | `PropagationDistance` + image chain |
| Alignment | `focus_alignment` | `SampleTop_Z` + image chain |
| Alignment | `center_alignment` | `Rotary`, `SampleTop_X` + image chain |
| Alignment | `roll_alignment` | `Rotary`, `Hexapod_Roll` + image chain |
| Alignment | `pitch_alignment` | `Rotary`, `Hexapod_Pitch` + image chain |
| Alignment | `detector_z_rail_alignment` | `DetectorTable` (`.AX` / `.AY`), `PropagationDistance` + image chain |
| Alignment | `slit_centering` | `ConditioningSlit` or `SampleSlit` + image chain |
| Characterization | `sensitivity_characterization` | `Hexapod_Roll`, `Hexapod_Pitch` |
| Characterization | `energy_characterization` | `Monochromator` (measured with the channel-cut-crystal [Subject](experiment.md)) |
| Characterization | `blade_throw_characterization` | `ConditioningSlit` or `SampleSlit` blades + image chain |
| Recovery | `hexapod_reboot` | `Hexapod` |
| Energy change | `energy_setting` | the energy-tracking facets (`Monochromator` Bragg arms + M2 offset, `SampleSlit` vertical pair) |

Image chain = `Camera`, `Scintillator`.

A few of these need more than a row.

### Calibrations recorded by alignment

An alignment is the act; when it settles on a value that downstream work later cites, that value is stored as a [Calibration](../../architecture/modules/calibration/index.md) appended with a `MeasuredSource` that names the Procedure. Three of the modeled Procedures mint one:

- `center_alignment` records a `rotation_center` on the rotary stage when it converges.
- `blade_throw_characterization` records a per-blade `blade_throw_scale` (pixels per mm) on the slit.
- `energy_characterization` records an `energy_offset` on the `Monochromator` (detailed under [Energy](#energy-setting-and-characterization) below).

The others do not, and the difference is principled rather than accidental: `detector_z_rail_alignment` re-establishes its converged `DetectorTable` angles as step-log setpoints (alignment state re-run each time, not a constant downstream reconstruction cites), the sample `roll` / `pitch` alignments re-derive their motor-sensitivity constants (`K_roll` / `K_pitch`) per run rather than persisting them (the open watch-item `STAGE-4`), and `resolution` / `focus` alignment settle a stage position with no value to store. In every case the centroid fit and convergence judgement live at the edge; CORA records the act and, where there is one, the resulting value.

### Energy: setting and characterization

`energy_setting` is the coordinating energy-change operation (the Procedure kind names the specific operation, distinct from the `cora.capability.energy_change` Capability code it realizes, as `motor_homing` sits under `maintenance`): given a target energy (a free keV value), it drives the energy-tracking optic axes together to their per-energy positions, reading each axis's [energy curve](inventory.md#energy-tracking-optic-axes). A Method declares the free-keV parameter; the Procedure expresses the coordinated move. It satisfies the `energy_configured` precondition stub listed under [From the 2-BM procedures source](#from-the-2-bm-procedures-source). Because the curves interpolate, an operator can request an energy between the configured saved points, not just the menu. The operator's `EnergyChange` Decision (modeled in the energy-change scenario) is the forward-looking justification; this Procedure is the motion record. The per-axis curve evaluation is now wired: the runtime interpolates a position for any requested energy (including a value between the saved points), and refuses an energy outside the calibrated range rather than clamping. Executing the coordinated move at the beamline still needs the deferred pieces tracked with the [energy curves](inventory.md#energy-tracking-optic-axes) (the real saved positions, the per-facet constituent wiring, and live EPICS dispatch), so today the Procedure records the move rather than driving it.

`energy_characterization` is the channel-cut-crystal energy calibration (staff-documented on the [docs2bm energy-calibration page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_022.html)): rock a crystal of known lattice spacing through its Bragg peak, fit the peak angle, and apply Bragg's law to recover the true beam energy. When it completes, the operator records the result as the `energy_offset` [Calibration](../../architecture/modules/calibration/index.md) on the `Monochromator`, appended with a `MeasuredSource` citing the Procedure: the signed correction (true minus commanded energy) at the measured energy. This is distinct from `energy_setting`: that operation *sets* the energy by driving the optic curves; this one *measures* whether the delivered energy matches the command. The offset is recorded in the energy domain and does not modify the [energy curves](inventory.md#energy-tracking-optic-axes); whether the energy-change IOC already folds it into the saved `store_0` table is the open question `ENERGY-8`, and whether the channel-cut crystal is current 2-BM practice is `ENERGY-7`. The channel-cut crystal is the measuring tool, modeled as a calibration [Subject](experiment.md) like the resolution phantom, not a target Asset.

### Staff-validated routines

`detector_z_rail_alignment`, `slit_centering`, and `blade_throw_characterization` are the three routines validated at the beamline in the [2bm-procedures source](#from-the-2-bm-procedures-source). CORA models them in its own lens rather than mirroring the staff scripts. `detector_z_rail_alignment` is the detector-table counterpart of `center_alignment`: an iterative walk along the propagation Z rail, rotating the `DetectorTable` angular axes (`.AX` / `.AY`) until the rail runs parallel to the beam. `slit_centering` centres the beam image on the detector through a slit, then closes the aperture to a target as steps inside the one act; it is named by its operation noun, not the staff verb-phrase `centre_and_close_slits`. `blade_throw_characterization` drives each blade by a known throw and records the per-blade pixels-per-mm slope it yields (see [Calibrations](#calibrations-recorded-by-alignment) above). The executable models are `test_2bm_detector_z_rail_alignment.py`, `test_2bm_slit_centering.py`, and `test_2bm_blade_throw_characterization.py`.

## Deferred

Two coordinated operations are design-locked but not yet conductible: each is gated on staff facts and hardware that have to land before it can carry real positions or drive anything.

### Beam mode change

`beam_mode_change` is a sibling of `energy_setting`. 2-BM runs two beam modes (the monochromator inserted vs bypassed, see [Beam modes](#beam-modes)), and switching between them is one coordinated multi-device move (DMM in/out, the mirror coating stripe with its table-X, downstream tracking) of the same Method + Procedure shape, with the target mode (mono or pink) as a parameter rather than two verb-first kinds, paired with a `BeamModeChange` Decision for the operator's choice. It is gated on the staff facts `MODE-1` / `MODE-2` / `MODE-3` and `MIRROR-1` before it can carry real positions or drive hardware.

### Beam alignment

Aligning the beam within each mode is a separate task from the sample and detector alignments [modeled above](#modeled-today): the `*_alignment` Procedures position the *sample* on the rotary stage against a beam that is already there, and `detector_z_rail_alignment` positions the *detector table*, while beam alignment positions the *beam itself*, walking it through the mask, mirror, and monochromator until it is centered and vertically symmetric on the viewing camera. The staff routine is the white-then-pink-then-mono sequence on the [docs2bm beamline-alignment page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_012.html).

CORA models this as a deferred `beam_alignment` Procedure family, one Procedure per beam mode:

| Procedure | Establishes | Target Assets |
| --- | --- | --- |
| `white_beam_alignment` | the raw bending-magnet beam centered through the fixed mask, with the mirror dropped flat and low and the DMM driven out | `Mask`, `Mirror` + alignment camera |
| `pink_beam_alignment` | the mirror raised to its pink-mode deflection so its coating stripe sets the high-energy cutoff, beam re-centered | `Mirror`, `MirrorTable` + alignment camera |
| `mono_beam_alignment` | both DMM crystals re-centered so the Bragg-selected beam lands on the detector (the second-crystal M2Y vertical-offset geometry) | `Monochromator` (Bragg arms + M2Y) + alignment camera |

Each one builds on the deferred `beam_mode_change` move above and then records the per-mode beam-finding steps. Most of the body is manual operator tuning: centering the beam, judging the vertical-intensity symmetry, requesting accelerator beam-steering corrections in small (about 10 microradian) steps, and re-optimizing the second crystal. That tuning lives at the edge; CORA's part is to record the act, its target Assets, and any resulting [Calibration](../../architecture/modules/calibration/index.md) (a mono alignment that settles on a measured crystal separation is the natural counterpart of `center_alignment` to `rotation_center`), not to drive the search. This is the intentional-modeling line: capture the durable structure of the task, do not mirror the staff's step-by-step ritual.

The family stays deferred for the same reasons as `beam_mode_change`: the DMM insert and bypass ceremony (`MODE-2`), the Pink saved positions and stripe map (`MODE-3` / `MIRROR-1`), and the two pieces this routine relies on that are not yet on file (the alignment camera `ALIGN-1` and the fixed mask `ALIGN-2`) all have to land first. It carries no steps or positions until then; see [Open questions](questions.md#beamline-alignment).

## Beam modes

Reference for the coordinated optic moves above. 2-BM runs in two beam modes, and the energy menus are mode-specific (see [Energy-tracking optic axes](inventory.md#energy-tracking-optic-axes)). In monochromatic mode the double-multilayer monochromator (DMM) is inserted and its crystals Bragg-select one energy (the Mono menu: 13.374, 13.574, 18.0, 20.0, 25.0, 25.584 keV; the energy curves are stamped `beam_mode = mono`). In pink (broadband) mode the DMM is driven out of the beam (its Y motors to about -10) and the Bragg arms park, so the full bending-magnet beam passes through; the mirror coating stripe (`2bma:m3`, with a coordinated mirror-table X move on `2bma:m1` / `m4`) then sets the high-energy cutoff (the Pink menu: 30, 40, 50, 60 keV). Diagnostics and downstream tracking follow the mode: the diagnostic flag (`2bma:m44`) is raised in Mono and parked in Pink, and the downstream table and B-station slits hold neutral in Pink. Source: the staff-authored [docs2bm components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html).

Switching between the modes is the `beam_mode_change` operation above. CORA does not yet model the switch or carry Pink positions: the energy IOC stores Mono and Pink as two saved configs, but only the Mono curves are seeded (Pink seeds when staff provide the Pink `store_0`, MODE-3), the named-stripe to m3-position map is unpublished (MIRROR-1), and the DMM insert and bypass ceremony is unrecorded (MODE-2). Per-mode energy curves are carried by the `beam_mode` operating-point key. This is deferred until the staff answers land; see [Open questions](questions.md#beam-mode).

## From the 2-BM procedures source

The [2bm-procedures](https://github.com/xray-imaging/2bm-procedures) repo ([rendered](https://docs2bm.readthedocs.io/en/latest/source/procedures.html)) is the staff-authored source for 2-BM procedures, the upstream this page adopts from. Three routines are validated at the beamline; CORA now models all three as Procedures (`detector_z_rail_alignment`, `slit_centering`, `blade_throw_characterization` in the [table above](#modeled-today)), and their target Assets are registered in the [inventory](inventory.md). Each staff procedure is structured as Name / Devices / Preconditions / Parameters / Steps / Postconditions / Failure modes; adopting that precondition-graph shape into the Operation BC `Procedure` aggregate is a future concern. The dependency graph for `detector_z_rail_alignment` is reproduced below as a first step, ahead of that modelling.

| Staff procedure (validated) | Target Assets | Note |
| --- | --- | --- |
| Detector Z-rail alignment to the beam | drives `PropagationDistance` (the Z walk on `2bmbAERO:m1`) and the `DetectorTable` angular axes (`2bmb:table3.AX` / `.AY`, the tilt correction); imaging chain `Scintillator` + `Camera` | Modeled as `detector_z_rail_alignment`. NOT the same as `roll_alignment` / `pitch_alignment`: those align the sample `Hexapod`, not the detector table. The staff `target_asset_ids` are `PropagationDistance`, `DetectorTable`, `Scintillator` (the staff name is `Scintillator_LuAG`; CORA keeps the material as a setting). |
| Centre and close an L3-style slit aperture | `ConditioningSlit` (A) or `SampleSlit` (B) | Modeled as `slit_centering` (named by its operation noun, not the staff verb-phrase). Runs on either L3 station (the `--slit-station` parameter, default B), not only the A-station slit; two-phase: centre on Hcenter / Vcenter, then sequential H / V size reduction as steps inside the one act. |
| Calibrate the throw of each L3 slit blade motor | `ConditioningSlit` (A) or `SampleSlit` (B) blade motors | Modeled as `blade_throw_characterization`, which mints the `blade_throw_scale` [Calibration](../../architecture/modules/calibration/index.md). Runs on either L3 station (default B); drive each blade by +/- blade_throw_mm, measure edge shift, fit per-blade slopes (the fit is downstream of CORA). |

The source also defines eight stub procedures as named targets for a precondition graph (each declares only its postcondition): `beamline_enabled`, `a_slits_open`, `energy_configured`, `flag_in_beam`, `b_shutter_open` (P6-50 safety shutter), `b_slits_configured`, `sample_out_of_beam`, `microscope_configured`. In the CORA lens most of these are already-modeled state, not new procedures to build: `energy_configured` is the postcondition of the `energy_setting` Procedure above, `b_shutter_open` is the `StationShutter` open state ([Shutter state at run start](experiment.md#shutter-state-at-run-start)), `sample_out_of_beam` is the operator assertion the [`flat_baseline`](recipes.md) recipe already relies on, `microscope_configured` is the microscope setup, and `a_slits_open` / `b_slits_configured` are slit state that `slit_centering` establishes. `flag_in_beam` (`2bma:m44`) is the one genuinely unmodeled stub: there is no flag Asset yet.

### Precondition graph for `detector_z_rail_alignment`

The staff source carries the preconditions as a machine-readable list (the `PRECONDITIONS` array in `detector_z_rail_alignment.py`): each entry is a postcondition *state*, a satisfying *procedure* that establishes it, an informal *predicate* over PVs, and a 2bm-docs spec page. The state name and the procedure name differ, which the flat list above blurs: the eight stubs are the states; the procedures that satisfy them are named in the second column here. This is the shape a future `Procedure.preconditions` would carry; it is reproduced so the dependency edges are explicit.

| Precondition state | Satisfying procedure | Predicate (representative PVs) | Spec |
| --- | --- | --- | --- |
| `beamline_enabled` | `enable_beamline` | `S02BM-PSS:StaA:SecureM` = 1 and `StaB:SecureM` = 1 and `FES:BeamBlockingM` = 0 and `SR-ACIS:2BM:FesPermitM` = 1 | item_003 |
| `a_slits_open` | `set_a_slits` | A-station H and V size RBV >= 0.5 mm (CORA descriptor: `2bma:Slit1Hsize` / `Slit1Vsize`) | item_004 |
| `energy_configured` | `set_energy_to_preselect` | Mirror M1 and DMM at the per-energy positions (energy lookup table) | item_005 |
| `flag_in_beam` | `set_flag_in` | `2bma:m44.RBV` at the mode/energy target (0 mm in pink) | item_006 |
| `b_shutter_open` | `open_b_shutter` | `S02BM-PSS:SBS:BeamBlockingM` = 0 (open; inverted enum, STATE 0 = not blocking) | item_007 |
| `b_slits_configured` | `set_b_slits` | B slits about 1.0 x 1.0 mm, centred on the energy-set vertical Y | item_008 |
| `sample_out_of_beam` | `move_sample_out_of_beam` | the mount-dependent sample axis at its out-of-beam position | item_009 |
| `microscope_configured` | `configure_microscope_for_alignment` | `2bm:MCTOptics:LensSelect` = 0 (1.1x slot), `2bmb:table3.Y` at the energy Y, and 200 <= `2bmbAERO:m1.RBV` <= 500 mm | item_010 |

Three further preconditions in the source have no dedicated procedure: `fes_shutter_open` (bundled into `enable_beamline`), `pss_interlocks_satisfied` (a sub-condition of `beamline_enabled`), and `mctoptics_ioc_reachable` (an infrastructure check: `caget` on `2bm:MCTOptics:CameraSelect` succeeds). Several predicates the staff left as TBD are already pinned by CORA's descriptor (the A-slit size PVs above are one example); folding those in is part of adopting the graph.
