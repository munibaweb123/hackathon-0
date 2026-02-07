#!/usr/bin/env python3
"""Demonstration of the complete Personal AI Employee system."""

import os
import tempfile
import time
from pathlib import Path
from src.ai_employee import AIEmployee


def demo_basic_workflow():
    """Demonstrate the basic workflow of the AI Employee."""
    print("=== Personal AI Employee Demo ===\n")

    # Create a temporary directory for the demo
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a simple config file
        config_content = f"""vault_path: "{temp_path}"
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

        print(f"1. Setting up AI Employee with vault at: {temp_path}")

        # Initialize the AI Employee
        ai_employee = AIEmployee(str(config_file))
        print("✓ AI Employee initialized successfully\n")

        # Show the vault structure
        print("2. Vault structure created:")
        for folder in ["inbox", "processing", "pending-approval", "completed", "rejected", "archive", "error"]:
            folder_path = temp_path / folder
            print(f"   - {folder}: {folder_path}")
        print()

        # Create a simple test document
        inbox_folder = temp_path / "inbox"
        test_doc = inbox_folder / "test_document.txt"
        with open(test_doc, 'w') as f:
            f.write("""# Sample Document

This is a sample document for the AI Employee to process.

It contains some content that the AI can analyze, summarize, and categorize.

The document is simple enough that it should be processed automatically without requiring human approval.
""")

        print(f"3. Created test document: {test_doc.name}")
        print(f"   Content: Simple document that should be auto-processed\n")

        # Show initial state
        print("4. Initial file state:")
        print(f"   - Inbox folder contains: {[f.name for f in inbox_folder.iterdir()]}")
        print()

        # Instead of running continuously, let's simulate processing by directly calling the processing logic
        print("5. Processing document...")

        # Since we can't run the full monitoring loop in a demo, let's demonstrate the core functionality
        from src.document_classifier import DocumentClassifier
        from src.entities import OperationEntity

        classifier = DocumentClassifier()
        file_type = classifier.classify_file(test_doc)
        processing_type = classifier.get_processing_recommendation(test_doc)

        print(f"   - Document classified as: {file_type}")
        print(f"   - Recommended processing: {processing_type}")

        # Check if document needs approval
        needs_approval, reason = ai_employee.document_processor.assess_complexity(test_doc)
        print(f"   - Needs approval: {needs_approval}")
        if needs_approval:
            print(f"   - Reason: {reason}")
        else:
            print(f"   - Reason: Simple document, no approval needed")
        print()

        # Demonstrate the information retrieval system
        print("6. Information retrieval system:")
        ai_employee.info_retrieval.index_file(test_doc)
        tags = ai_employee.info_retrieval.get_tags()
        print(f"   - Indexed document: {test_doc.name}")
        print(f"   - Available tags: {tags}")

        # Search for content
        results = ai_employee.info_retrieval.search("sample document")
        print(f"   - Search results for 'sample document': {len(results)} matches")
        print()

        # Demonstrate task management
        print("7. Task management system:")
        task_list = ai_employee.task_manager.create_task_list("demo_tasks", "Demo task list")
        task_list.add_task("Process document", "Process the sample document", "high")
        task_list.add_task("Generate summary", "Create a summary of the document", "normal")

        print(f"   - Created task list: {task_list.name}")
        print(f"   - Tasks created: {len(task_list.tasks)}")

        # Save the task list
        ai_employee.task_manager.save_task_list("demo_tasks")
        print(f"   - Task list saved to processing folder")
        print()

        # Show security compliance
        print("8. Security and compliance:")
        is_compliant = ai_employee.constraint_checker.verify_bronze_tier_compliance()
        print(f"   - Bronze tier compliance: {'✓ PASS' if is_compliant else '✗ FAIL'}")

        # Show file path validation
        is_safe = ai_employee.security_enforcer.is_path_allowed(str(test_doc))
        print(f"   - Path validation for {test_doc.name}: {'✓ ALLOWED' if is_safe else '✗ BLOCKED'}")
        print()

        print("=== Demo Complete ===")
        print("The Personal AI Employee system has been successfully demonstrated!")
        print("- Document processing workflow")
        print("- Information retrieval capabilities")
        print("- Task management features")
        print("- Security and compliance checking")
        print("- File system boundary enforcement")


if __name__ == "__main__":
    demo_basic_workflow()