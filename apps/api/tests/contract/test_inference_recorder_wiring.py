"""Contract test: the composition root wires a real inference recorder.

The Kernel defaults `inference_recorder` to the no-op `NullInferenceRecorder`;
`cora.api.main` must override it (via `dataclasses.replace` after
`wire_decision`) with the `DelegatingInferenceRecorder` that forwards to the
`append_inferences` handler. Without this assertion a regression that dropped
the override would silently revert production to the no-op recorder, dropping
all agent model-provenance with the rest of the suite still green.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api._inference_recorder import DelegatingInferenceRecorder
from cora.api.main import create_app


@pytest.mark.contract
def test_app_wires_delegating_inference_recorder_on_the_kernel() -> None:
    app = create_app()
    with TestClient(app):
        recorder = app.state.deps.inference_recorder
    assert isinstance(recorder, DelegatingInferenceRecorder)
