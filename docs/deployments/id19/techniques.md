# Techniques

*What CORA would run at ID19: hard X-ray parallel-beam microtomography, radiography, and propagation phase-contrast imaging, a [Catalog](../../catalog/methods.md) Method bound through an [ESRF Practice](../esrf/index.md#the-techniques-adapted-here). The technique is plain tomography reuse; the genuine novelty at ID19 is the control floor, not the science.*

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Parallel-beam microtomography / radiography / phase-contrast imaging | `tomography` | the sample is spun through the beam while an area detector records a stack of projection radiographs; a real-space volume is reconstructed downstream. The existing Method the 2-BM pilot and MAX IV TomoWise carry; ID19 is a further consumer (TECH-1) |

The technique is recorded as a pending [Practice](../esrf/index.md#the-techniques-adapted-here) on the ESRF Site, `ID19_microtomography_practice` (TECH-1).

## The acquisition shape

Microtomography is an acquisition shape CORA already models. The [rotation stage](equipment/sample.md) spins the sample through the beam; the [detector](equipment/detector.md) records a projection radiograph at each angle; and the stack of projections, together with the known rotation angles, is enough to reconstruct a real-space volume of the sample. ID19's long source-to-sample distance gives the beam high spatial coherence, so a settable sample-to-detector distance turns the same acquisition into propagation phase-contrast imaging (DET-1). The reconstruction, turning the projection stack into a volume, is `ComputePort` work, not a beamline device, the same reconstruction leg the other imaging beamlines carry.

ID19 runs this acquisition at two endstations sharing one source and optics: the micro-resolution (MR) station for large-field, high-throughput tomography, and the high-resolution (HR) station for small-field, high-resolution tomography. Both are the same Method; the difference is the stage stack and the magnification optic, a Practice-and-settings difference, not a new technique.

So the parts are a `RotaryStage` (the tomographic spin, the master motion, SAMPLE-1), a `LinearStage` for sample centring (SAMPLE-1), a `Camera` as the area detector (interchangeable Frelon / PCO / Basler Lima cameras, DET-1), and a `LinearStage` setting the detector propagation distance (DET-1). None is new; ID19 reuses the existing tomography device shapes exactly.

## Why the technique is not the novelty

ID19 is a microtomography beamline, and CORA already models microtomography at the 2-BM operational pilot and the MAX IV TomoWise design scaffold. The `tomography` Method, its Capability, and the device families it binds are all in place. ID19 is a further consumer of that Method, not a new technique, so the Practice is carried pending only because ID19 is not yet driven by CORA, not because the Method is new (TECH-1).

The genuine novelty at ID19 is one layer down, in the control plane: ESRF runs BLISS (a Tango-based control system), not EPICS, and ID19 is the first to bring that BLISS floor to tomographic imaging (its ESRF sibling ID32 opened it for soft X-ray RIXS). That is a [Controls](equipment/controls.md) and seam concern, not a technique concern. Holding the technique constant is the point: it isolates the control-plane axis so the BLISS / Tango floor is the only thing that is new (see [Model](model.md)).

## Not modelled yet

This cut models the source, the optics, and the two main tomography endstations (MR and HR). The further endstations present in the ID19 config are noted but not modelled:

- The MH and MED tomography endstations, their own BLISS sessions with their own stage stacks (ENDSTATION-1).
- The LATOMO laminography endstation, which runs a MicosAnka controller over TCP plus a tilt-transformation pusher, a distinct acquisition geometry (ENDSTATION-1).
- The RADIO (radiography) and PCOTOMO (PCO high-speed tomography) sessions (ENDSTATION-1).
- The SmarAct multi-tower sample stack and the FalconX / Mercury fluorescence MCAs (ENDSTATION-1).

Each is named on the [Open questions](questions.md) page rather than modelled speculatively. The source walk that grounds what is and is not present is the generated [beamline](beamline.md) view.
