from __future__ import annotations

import io
import json
import hashlib
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from src.download_data import _extract_expected_workbook, download_uci_workbook


EXPECTED = {
    "InvoiceNo": ["10001"],
    "StockCode": ["12345"],
    "Description": ["Fixture item"],
    "Quantity": [2],
    "InvoiceDate": ["2010-01-01 10:00:00"],
    "UnitPrice": [4.5],
    "CustomerID": [12345],
    "Country": ["United Kingdom"],
}


def _valid_workbook_bytes() -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(EXPECTED).to_excel(writer, sheet_name="Year 1", index=False)
    return buffer.getvalue()


def _zip_bytes(member_name: str = "online_retail_II.xlsx", payload: bytes | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, payload if payload is not None else _valid_workbook_bytes())
    return buffer.getvalue()


class _FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_download_extracts_only_expected_file_and_passes_schema_gate(tmp_path, monkeypatch):
    import src.download_data as downloader

    payload = _zip_bytes("nested/online_retail_II.xlsx")
    monkeypatch.setattr(downloader.urllib.request, "urlopen", lambda *args, **kwargs: _FakeResponse(payload))
    monkeypatch.setattr(downloader.time, "sleep", lambda *_: None)

    raw_dir = tmp_path / "raw"
    output = raw_dir / "online_retail_II.xlsx"
    result = download_uci_workbook(raw_dir=raw_dir, workbook_path=output, download_url="https://fixture.invalid/file.zip")

    assert result == output
    assert output.exists() and output.stat().st_size > 0
    assert (raw_dir / "online_retail_ii.zip").exists()
    manifest = json.loads((raw_dir / "source_manifest.json").read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    assert manifest["workbook"]["sha256"] == expected_hash
    assert manifest["license"] == "CC BY 4.0"
    workbook = pd.ExcelFile(output)
    assert workbook.sheet_names == ["Year 1"]
    assert len(pd.read_excel(workbook, sheet_name="Year 1")) == 1


def test_existing_workbook_is_not_overwritten_without_force(tmp_path, monkeypatch):
    import src.download_data as downloader

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    output = raw_dir / "online_retail_II.xlsx"
    output.write_bytes(b"existing")
    monkeypatch.setattr(downloader.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("unexpected network request"))

    assert download_uci_workbook(raw_dir=raw_dir, workbook_path=output) == output
    assert output.read_bytes() == b"existing"


def test_archive_without_expected_workbook_is_rejected(tmp_path):
    archive_path = tmp_path / "bad.zip"
    archive_path.write_bytes(_zip_bytes("other.xlsx"))
    with pytest.raises(ValueError, match="Expected exactly one"):
        _extract_expected_workbook(archive_path, tmp_path, tmp_path / "out.xlsx")


def test_non_zip_download_is_rejected(tmp_path):
    archive_path = tmp_path / "not_a_zip.zip"
    archive_path.write_text("not really a zip", encoding="utf-8")
    with pytest.raises(ValueError, match="not a valid ZIP"):
        _extract_expected_workbook(archive_path, tmp_path, tmp_path / "out.xlsx")


def test_transient_download_error_is_retried(tmp_path, monkeypatch):
    import urllib.error
    import src.download_data as downloader

    payload = _zip_bytes()
    attempts = {"count": 0}

    def flaky_urlopen(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise urllib.error.URLError("temporary network failure")
        return _FakeResponse(payload)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", flaky_urlopen)
    monkeypatch.setattr(downloader.time, "sleep", lambda *_: None)
    raw_dir = tmp_path / "raw"
    result = download_uci_workbook(raw_dir=raw_dir, workbook_path=raw_dir / "online_retail_II.xlsx",
                                   download_url="https://fixture.invalid/file.zip", retries=2)
    assert attempts["count"] == 2
    assert result.exists()
