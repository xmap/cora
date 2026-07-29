"""Vertical slice for the `IngestScan` command.

Module-as-namespace surface:

    from cora.data.features import ingest_scan

    cmd = ingest_scan.IngestScan(
        locator="file:///data2/2026-07/pi-12345/scan_001.h5",
        producing_asset_id=...,
        supply_id=...,
        access_protocol="posix",
    )
    dataset_id = await ingest_scan.bind(deps)(cmd, principal_id=...)

The ONE slice that turns an on-disk scan file into the Data BC's
records: it reads the file through the ScanReader port, digests it
through the ChecksumComputer port, and composes the register_dataset,
register_distribution, and record_acquisition DECIDERS into a single
atomic `append_streams` write. It never chains those slices' handlers;
each handler is its own transaction and a mid-chain rejection would
strand a Dataset without its Acquisition.
"""

from cora.data.features.ingest_scan import tool
from cora.data.features.ingest_scan.command import IngestScan
from cora.data.features.ingest_scan.handler import Handler, IdempotentHandler, bind
from cora.data.features.ingest_scan.route import router

__all__ = ["Handler", "IdempotentHandler", "IngestScan", "bind", "router", "tool"]
