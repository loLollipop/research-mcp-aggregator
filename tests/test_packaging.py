"""Release packaging tests."""

import importlib.metadata as metadata

import pytest

import research_mcp


def test_package_version_is_non_empty() -> None:
    assert isinstance(research_mcp.__version__, str)
    assert research_mcp.__version__


def test_console_script_entry_point_when_metadata_available() -> None:
    try:
        metadata.version("research-mcp")
    except metadata.PackageNotFoundError:
        pytest.skip("research-mcp package metadata is not installed")

    entry_points = [
        entry
        for entry in metadata.entry_points(group="console_scripts")
        if entry.name == "research-mcp"
    ]
    assert entry_points
    assert entry_points[0].value == "research_mcp.server:main"
