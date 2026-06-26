"""InMemoryDecidePort: a test fake for the DecidePort seam.

A deterministic, stateless fake that replays a pre-seeded sequence of
`SteeringAdvice`, indexed by `SteeringEvidence.iteration_index`, then advises
`Stop` once the sequence is exhausted. It is the DecidePort analogue of
`InMemoryControlPort` / `InMemoryComputePort`: the seam is reachable in a
test without any real brain, and the loop terminates by construction.

Stateless on purpose, to honor the port's stateless-brain contract: the
advice for a turn is `seq[evidence.iteration_index]`, derived from the evidence
the caller hands over, not from an internal cursor. The same fake therefore
behaves identically on a replay that re-drives earlier turns.

`set_advice_sequence` is an adapter-only test hook, deliberately NOT on the
`DecidePort` Protocol: production callers never seed advice.
"""

from collections.abc import Sequence

from cora.operation.ports.decide_port import (
    SteeringAdvice,
    SteeringEvidence,
    SteeringVerdict,
)


class InMemoryDecidePort:
    """A stateless fake decider that replays seeded advice by iteration.

    Satisfies the `DecidePort` Protocol (structurally; `@runtime_checkable`
    `isinstance` passes). Seed a sequence with `set_advice_sequence`; each
    `advise_next` returns `seq[evidence.iteration_index]`, and once the iteration
    index runs past the seeded sequence it returns a `Stop` verdict so a
    driven loop ends. With no sequence seeded it advises `Stop` immediately.
    """

    def __init__(self) -> None:
        self._advice: tuple[SteeringAdvice, ...] = ()
        self._received: list[SteeringEvidence] = []

    def set_advice_sequence(self, advice: Sequence[SteeringAdvice]) -> None:
        """Seed the advice this fake will replay, in iteration order.

        Adapter-only test hook (not on the Protocol). Each entry is returned
        for the matching `SteeringEvidence.iteration_index`; past the end the fake
        advises `Stop`.
        """
        self._advice = tuple(advice)

    @property
    def received_evidence(self) -> tuple[SteeringEvidence, ...]:
        """The evidence handed to `advise_next`, in call order.

        Test-observability hook (not on the Protocol): a test can assert what
        the loop showed the brain, e.g. that each observation's `point` records
        the coordinates the pass actually measured at. Recording it does not
        affect advice selection, which stays stateless.
        """
        return tuple(self._received)

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Return the seeded advice for `evidence.iteration_index`, else `Stop`.

        Stateless: the turn is selected by the iteration the caller reports,
        not an internal cursor, so a replayed earlier turn yields the same
        advice.
        """
        self._received.append(evidence)
        if 0 <= evidence.iteration_index < len(self._advice):
            return self._advice[evidence.iteration_index]
        return SteeringAdvice(verdict=SteeringVerdict.STOP)

    async def aclose(self) -> None:
        """No-op: the fake holds no resources."""
        return None


__all__ = ["InMemoryDecidePort"]
