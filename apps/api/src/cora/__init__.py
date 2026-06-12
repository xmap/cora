"""CORA: research facility system of record."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cora")
except PackageNotFoundError:  # pragma: no cover  # uninstalled / dev mode without -e
    __version__ = "0.0.0+unknown"
