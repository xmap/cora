"""Operation BC adapters.

`InMemoryControlPort` is the unit-tier `ControlPort` adapter per
[[project_control_port_generalization_research]]. Substrate adapters
(`CaprotoControlPort` test-tier; `EpicsCaControlPort`,
`EpicsPvaControlPort` production-tier) cover the EPICS family, and
`TangoControlPort` (PyTango, optional `tango` extra) covers Tango-floor
deployments. `ControlPortRegistry` routes addresses to the right
substrate by longest-prefix match so the executor sees a single
`ControlPort` regardless of how many substrates a deployment runs.
"""
