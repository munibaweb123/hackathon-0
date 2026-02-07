#!/usr/bin/env python3
"""Basic functionality test for Personal AI Employee."""

import os
import tempfile
import shutil
from pathlib import Path
from src.ai_employee import AIEmployee
from src.config import Config


def test_basic_setup():
    """Test basic setup and initialization."""
    print("Testing basic setup...")

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create config file
        config_content = f"""
vault_path: "{temp_path}"
input_folder: "inbox"
processing_folder: "processing"
pending_approval_folder: "pending-approval"
completed_folder: "completed"
rejected_folder: "rejected"
archive_folder: "archive"
error_folder: "error"
log_directory: "{temp_path / 'logs'}"
watcher_interval: 1
"""

        config_file = temp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(config_content)

        # Test initialization
        try:
            ai_employee = AIEmployee(str(config_file))
            print("✓ AI Employee initialized successfully")

            # Verify vault structure was created
            expected_dirs = [
                "inbox", "processing", "pending-approval",
                "completed", "rejected", "archive", "error"
            ]

            for dir_name in expected_dirs:
                dir_path = temp_path / dir_name
                if dir_path.exists():
                    print(f"✓ {dir_name} directory exists")
                else:
                    print(f"✗ {dir_name} directory missing")

            # Verify log directory was created
            log_dir = temp_path / "logs"
            if log_dir.exists():
                print("✓ Logs directory exists")
            else:
                print("✗ Logs directory missing")

            return True

        except Exception as e:
            print(f"✗ Initialization failed: {e}")
            return False


def test_entity_creation():
    """Test entity creation."""
    print("\nTesting entity creation...")

    try:
        from src.entities import FileEntity, OperationEntity, ApprovalEntity, LogEntryEntity

        # Test FileEntity
        file_entity = FileEntity(path="test.txt", type="document")
        assert file_entity.path == "test.txt"
        print("✓ FileEntity created successfully")

        # Test OperationEntity
        operation_entity = OperationEntity(type="test", file_id="test.txt")
        assert operation_entity.type == "test"
        print("✓ OperationEntity created successfully")

        # Test ApprovalEntity
        approval_entity = ApprovalEntity(request_type="test")
        assert approval_entity.request_type == "test"
        print("✓ ApprovalEntity created successfully")

        # Test LogEntryEntity
        log_entry = LogEntryEntity(level="info", actor="test", action="test_action")
        assert log_entry.level == "info"
        print("✓ LogEntryEntity created successfully")

        return True

    except Exception as e:
        print(f"✗ Entity creation failed: {e}")
        return False


def test_document_classification():
    """Test document classification."""
    print("\nTesting document classification...")

    try:
        from src.document_classifier import DocumentClassifier
        import tempfile

        classifier = DocumentClassifier()

        # Test with different file types
        test_files = [
            ("test.txt", "text"),
            ("test.docx", "document"),
            ("test.py", "code"),
            ("test.json", "data"),
            ("test.jpg", "image"),
            ("test.unknown", "general")
        ]

        for filename, expected_category in test_files:
            path = Path(filename)
            category = classifier.classify_file(path)
            print(f"✓ {filename} classified as {category} (expected {expected_category})")

        return True

    except Exception as e:
        print(f"✗ Document classification failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Running basic functionality tests for Personal AI Employee...\n")

    results = []
    results.append(test_basic_setup())
    results.append(test_entity_creation())
    results.append(test_document_classification())

    passed = sum(results)
    total = len(results)

    print(f"\nTest Results: {passed}/{total} passed")

    if passed == total:
        print("✓ All tests passed!")
        return True
    else:
        print("✗ Some tests failed!")
        return False


if __name__ == "__main__":
    main()