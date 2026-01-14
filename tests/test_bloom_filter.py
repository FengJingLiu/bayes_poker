from __future__ import annotations

import pytest


def test_pybloomfilter_add_and_open(tmp_path) -> None:
    pybloomfilter = pytest.importorskip("pybloomfilter")
    BloomFilter = pybloomfilter.BloomFilter

    bloom_path = tmp_path / "hand_hashes.bloom"
    bf = BloomFilter(1_000, 0.01, str(bloom_path))
    try:
        assert bf.add("00" * 16) is False
        assert bf.add("00" * 16) is True
    finally:
        bf.close()

    opened = BloomFilter.open(str(bloom_path))
    try:
        assert ("00" * 16) in opened
    finally:
        opened.close()
