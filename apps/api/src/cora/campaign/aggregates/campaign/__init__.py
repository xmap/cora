"""Campaign aggregate: state, enums (status / intent), bounded-text VOs,
errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.campaign.features.<verb>_campaign/` and import from here for
state and event types.

Public surface: enums + VOs + errors + events + evolver +
load_campaign. 6i-a shipped the foundation (register + get + 5 FSM
transitions: start / hold / resume / close / abandon); 6i-b added
the projection + list slice; 6i-c adds the cross-aggregate
membership slices (add_run / remove_run) plus Run aggregate
evolution (additive `campaign_id` field).
"""

from cora.campaign.aggregates.campaign.events import (
    CampaignAbandoned,
    CampaignClosed,
    CampaignEvent,
    CampaignHeld,
    CampaignRegistered,
    CampaignResumed,
    CampaignRunAdded,
    CampaignRunRemoved,
    CampaignStarted,
    deserialize_external_ref,
    event_type_name,
    from_stored,
    serialize_external_ref,
    to_payload,
)
from cora.campaign.aggregates.campaign.evolver import evolve, fold
from cora.campaign.aggregates.campaign.read import load_campaign
from cora.campaign.aggregates.campaign.state import (
    CAMPAIGN_DESCRIPTION_MAX_LENGTH,
    CAMPAIGN_EXTERNAL_ID_MAX_LENGTH,
    CAMPAIGN_NAME_MAX_LENGTH,
    CAMPAIGN_TAG_MAX_LENGTH,
    Campaign,
    CampaignAlreadyExistsError,
    CampaignCannotAbandonError,
    CampaignCannotAddRunError,
    CampaignCannotCloseError,
    CampaignCannotHoldError,
    CampaignCannotRemoveRunError,
    CampaignCannotResumeError,
    CampaignCannotStartError,
    CampaignDescription,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignRunAlreadyMemberError,
    CampaignRunNotMemberError,
    CampaignStatus,
    CampaignTag,
    InvalidCampaignAbandonReasonError,
    InvalidCampaignDescriptionError,
    InvalidCampaignExternalIdError,
    InvalidCampaignHoldReasonError,
    InvalidCampaignNameError,
    InvalidCampaignRunRemoveReasonError,
    InvalidCampaignTagError,
)

__all__ = [
    "CAMPAIGN_DESCRIPTION_MAX_LENGTH",
    "CAMPAIGN_EXTERNAL_ID_MAX_LENGTH",
    "CAMPAIGN_NAME_MAX_LENGTH",
    "CAMPAIGN_TAG_MAX_LENGTH",
    "Campaign",
    "CampaignAbandoned",
    "CampaignAlreadyExistsError",
    "CampaignCannotAbandonError",
    "CampaignCannotAddRunError",
    "CampaignCannotCloseError",
    "CampaignCannotHoldError",
    "CampaignCannotRemoveRunError",
    "CampaignCannotResumeError",
    "CampaignCannotStartError",
    "CampaignClosed",
    "CampaignDescription",
    "CampaignEvent",
    "CampaignHeld",
    "CampaignIntent",
    "CampaignName",
    "CampaignNotFoundError",
    "CampaignRegistered",
    "CampaignResumed",
    "CampaignRunAdded",
    "CampaignRunAlreadyMemberError",
    "CampaignRunNotMemberError",
    "CampaignRunRemoved",
    "CampaignStarted",
    "CampaignStatus",
    "CampaignTag",
    "InvalidCampaignAbandonReasonError",
    "InvalidCampaignDescriptionError",
    "InvalidCampaignExternalIdError",
    "InvalidCampaignHoldReasonError",
    "InvalidCampaignNameError",
    "InvalidCampaignRunRemoveReasonError",
    "InvalidCampaignTagError",
    "deserialize_external_ref",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_campaign",
    "serialize_external_ref",
    "to_payload",
]
