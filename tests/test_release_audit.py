import tempfile
import unittest
from pathlib import Path

from tools.release_audit import MAX_FILE_BYTES, REQUIRED_FILES, audit_tree


class ReleaseAuditTests(unittest.TestCase):
    def make_tree(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in REQUIRED_FILES:
            content = "Apache License\n" if name == "LICENSE" else "public release file\n"
            (root / name).write_text(content, encoding="utf-8")
        return root

    def test_minimal_allowlisted_tree_passes(self):
        self.assertEqual([], audit_tree(self.make_tree()))

    def test_forbidden_directory_fails(self):
        root = self.make_tree()
        (root / "references").mkdir()
        (root / "references" / "paper.txt").write_text("copied article", encoding="utf-8")
        self.assertTrue(any("forbidden" in failure or "unapproved" in failure for failure in audit_tree(root)))

    def test_symlink_fails(self):
        root = self.make_tree()
        (root / "docs").mkdir()
        (root / "docs" / "link.md").symlink_to(root / "README.md")
        self.assertTrue(any("symlink" in failure for failure in audit_tree(root)))

    def test_oversized_file_fails(self):
        root = self.make_tree()
        (root / "docs").mkdir()
        (root / "docs" / "oversized.md").write_text("x" * (MAX_FILE_BYTES + 1), encoding="utf-8")
        self.assertTrue(any("exceeds" in failure for failure in audit_tree(root)))

    def test_personal_machine_path_and_signed_url_fail(self):
        root = self.make_tree()
        machine_path = "/Use" + "rs/private-name/secret"
        signed_url = "https://x.invalid/?X-Amz-" + "Signature=abc"
        (root / "README.md").write_text(f"{machine_path}\n{signed_url}", encoding="utf-8")
        failures = audit_tree(root)
        self.assertTrue(any("home path" in failure for failure in failures))
        self.assertTrue(any("signed URL" in failure for failure in failures))

    def test_missing_license_fails(self):
        root = self.make_tree()
        (root / "LICENSE").unlink()
        self.assertTrue(any("missing required release file: LICENSE" in failure for failure in audit_tree(root)))

    def test_undeclared_asset_fails(self):
        root = self.make_tree()
        (root / "download.pdf").write_bytes(b"not really a PDF")
        failures = audit_tree(root)
        self.assertTrue(any("unapproved root file" in failure for failure in failures))
        self.assertTrue(any("forbidden file type" in failure for failure in failures))

    def test_unknown_root_file_fails(self):
        root = self.make_tree()
        (root / "private-notes.txt").write_text("internal", encoding="utf-8")
        self.assertTrue(any("unapproved root file" in failure for failure in audit_tree(root)))


if __name__ == "__main__":
    unittest.main()
