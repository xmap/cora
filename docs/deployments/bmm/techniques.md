# Techniques

*What CORA would run at BMM: X-ray absorption spectroscopy, bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here). BMM raises the spectroscopy Capability question CORA has not yet had to answer.*

BMM does transmission and fluorescence XAS / EXAFS: sweep the beam energy across an element's absorption edge, record the per-energy detector readings, and fit the absorption spectrum downstream.

| BMM technique | CORA expression | Earn-the-abstraction call |
| --- | --- | --- |
| Transmission XAS / EXAFS | an energy sweep reading I0/It/Ir | the live question (ENERGY-1): coin `energy_scan`, or hold under `characterization`? |
| Fluorescence XAS | the same sweep reading the `EnergyDispersiveSpectrometer` | same Capability, different detector in the slot |
| Energy calibration | reference foil + `Ir` channel each scan | a Calibration, not a separate technique |
| Alignment | beam-finding and slit/mirror tuning | reuse [`alignment`](../../catalog/methods.md) |

## The energy_scan Capability question (ENERGY-1)

BMM is the first CORA deployment whose measurement *is* an energy scan. The catalog already anticipates this: alongside `cora.capability.energy_change` (a coordinated *setpoint* move to one energy), a note records `cora.capability.energy_scan` as **pending in code**, and describes energy_change as "distinct from a future energy_scan sweep." BMM is that future consumer.

Per the design-phase discipline (Diamond i03/i22, 32-ID, and HXN all coined no new Capability at scaffold time), this scaffold **defers** coining `energy_scan`: an XAS scan is mapped to `characterization` plus `energy_change` for now, and the Capability is coined when a conduct-path actually sweeps the energy. The argument to coin is strong (the sweep is the measurement, exactly the in-kind case), and the catalog already reserved the name; it is held open deliberately, not because it is weak, but because a Capability is coined when a conduct-path forces it, not at scaffold time.

EXAFS data reduction (background subtraction, normalization, the chi(k) transform) is a `ComputePort` leg, not a beamline Method, the same way tomographic and ptychographic reconstruction are.
