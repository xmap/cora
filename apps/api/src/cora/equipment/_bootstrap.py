"""BC-level bootstrap re-exports and startup-time configuration checks.

Preserves the import path
`cora.equipment._bootstrap.SYSTEM_PRINCIPAL_ID` used by Equipment's
MCP tools. The constant itself lives at
`cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID` since the
post-Phase-3 cleanup hoisted both BCs' identical fallback constants
to one canonical home.

`check_pidinst_landing_page_template` is called from
`wire_equipment` at startup. Failing here keeps the PIDINST view
assembler free of per-request guards: if the template is missing,
the process never finishes booting and the route is unreachable. See
L12 + L17 of project_asset_persistent_id_design.
"""

from cora.infrastructure.config import Settings
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID


def check_pidinst_landing_page_template(settings: Settings) -> None:
    """Refuse to boot when the PIDINST landing-page template is empty.

    The PIDINST read route formats `landing_page_template` with the
    target asset's id to produce PIDINST v1.0 Property 3
    `landingPage`. An empty template would silently produce an empty
    landing page string and the serializer's `LandingPageMissingError`
    would fire on every request instead of at startup. Raising
    here makes the misconfiguration visible at boot.
    """
    if not settings.landing_page_template or not settings.landing_page_template.strip():
        raise RuntimeError(
            "Settings.landing_page_template must be non-empty: the PIDINST read "
            "route formats it with the target asset_id to produce the landing-page "
            "URL. Set LANDING_PAGE_TEMPLATE in the environment."
        )


__all__ = ["SYSTEM_PRINCIPAL_ID", "check_pidinst_landing_page_template"]
