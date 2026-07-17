"""Raw-byte SHA-256 tests."""

import hashlib
from pathlib import Path

import pytest

from echomind.parsers.errors import ParserError
from echomind.parsers.hashing import DEFAULT_CHUNK_SIZE, hash_file


def test_same_file_hash_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic bytes")

    assert hash_file(path) == hash_file(path)


def test_content_change_changes_hash(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"first")
    first_hash = hash_file(path)
    path.write_bytes(b"second")

    assert hash_file(path) != first_hash


def test_hash_uses_original_bytes(tmp_path: Path) -> None:
    raw = b"line one\r\nline two\r\n"
    path = tmp_path / "synthetic.txt"
    path.write_bytes(raw)

    assert hash_file(path) == hashlib.sha256(raw).hexdigest()


def test_hash_reads_more_than_one_chunk(tmp_path: Path) -> None:
    raw = b"x" * (DEFAULT_CHUNK_SIZE * 2 + 17)
    path = tmp_path / "large-synthetic.bin"
    path.write_bytes(raw)

    assert hash_file(path) == hashlib.sha256(raw).hexdigest()


def test_unreadable_path_returns_safe_error(tmp_path: Path) -> None:
    missing = tmp_path / "private-parent" / "missing.json"

    with pytest.raises(ParserError) as captured:
        hash_file(missing)

    error = captured.value
    assert error.error_code == "file_read_error"
    assert error.safe_filename == "missing.json"
    assert str(tmp_path) not in str(error)
