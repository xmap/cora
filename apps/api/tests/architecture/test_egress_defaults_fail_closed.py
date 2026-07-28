"""The egress + spend default ships SAFE: a blank deployment calls no model.

Sibling to `test_actuation_defaults_fail_closed`, for the other axis. That
one pins the defaults that keep CORA from moving hardware; this one pins the
default that keeps experiment metadata inside the facility and the token bill
at zero.

`llm_enabled` defaults False, so the LLM-backed subscribers (RunDebriefer,
CautionDrafter) do not register and nothing calls an external model. The flag
exists because the credential alone used to be enough: an `ANTHROPIC_API_KEY`
present in the environment for an unrelated reason silently switched on
outbound calls on EVERY terminal Run. Every one of the ~13 sibling
subscribers already carried its own default-off flag; this seam was the
outlier.

## Why the DECLARED default, not an instantiated Settings

Reading `model_fields[...].default` asserts what SHIPS, immune to whatever
the process environment happens to hold. `Settings()` would only tell us
about this shell.
"""

import pytest

from cora.infrastructure.config import Settings


@pytest.mark.architecture
def test_llm_default_is_off() -> None:
    assert Settings.model_fields["llm_enabled"].default is False
