"""Unit tests for attachment file validation (size + type allowlist).

Covers spec.md "Feature: File Attachments" validation contract:
- files over 10 MB are rejected
- disallowed extensions (executables/scripts) are rejected
- common business types are accepted
"""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from common.validators import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_SIZE,
    validate_attachment_file,
)


class TestValidateAttachmentFile:
    def _file(self, name, size=10):
        return SimpleUploadedFile(name, b"x" * size, content_type="application/octet-stream")

    def test_allowed_types_pass(self):
        for ext in ["pdf", "docx", "xlsx", "png", "jpg", "csv", "txt", "zip"]:
            # should not raise
            validate_attachment_file(self._file(f"report.{ext}"))

    def test_disallowed_extension_rejected(self):
        for ext in ["exe", "sh", "bat", "js", "msi", "dll"]:
            with pytest.raises(ValidationError):
                validate_attachment_file(self._file(f"malware.{ext}"))

    def test_no_extension_rejected(self):
        with pytest.raises(ValidationError):
            validate_attachment_file(self._file("README"))

    def test_extension_case_insensitive(self):
        # uppercase extension of an allowed type must pass
        validate_attachment_file(self._file("Scan.PDF"))

    def test_oversize_rejected(self):
        big = SimpleUploadedFile(
            "big.pdf", b"x" * (MAX_ATTACHMENT_SIZE + 1), content_type="application/pdf"
        )
        with pytest.raises(ValidationError):
            validate_attachment_file(big)

    def test_at_limit_passes(self):
        at_limit = SimpleUploadedFile(
            "ok.pdf", b"x" * MAX_ATTACHMENT_SIZE, content_type="application/pdf"
        )
        validate_attachment_file(at_limit)

    def test_double_extension_smuggling_rejected(self):
        # final extension is allowed but an inner segment is an executable
        for name in ["invoice.exe.pdf", "report.sh.png", "data.js.csv", "x.bat.docx"]:
            with pytest.raises(ValidationError):
                validate_attachment_file(self._file(name))

    def test_legit_dotted_name_passes(self):
        # dots that are not dangerous extensions are fine
        validate_attachment_file(self._file("2026.q1.report.pdf"))

    def test_none_is_noop(self):
        validate_attachment_file(None)

    def test_allowlist_excludes_executables(self):
        assert "exe" not in ALLOWED_ATTACHMENT_EXTENSIONS
        assert "sh" not in ALLOWED_ATTACHMENT_EXTENSIONS
        assert "pdf" in ALLOWED_ATTACHMENT_EXTENSIONS
