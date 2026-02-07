#!/usr/bin/env python3
"""Simple polling-based file monitor for testing."""

import time
import os
from pathlib import Path
from src.ai_employee import AIEmployee

def simple_monitor():
    print("Starting simple polling-based file monitor...")
    print("This will check the inbox folder every second for new files.")

    # Initialize AI Employee
    ai_employee = AIEmployee()

    inbox_path = Path("obsidian-vault/inbox/")
    processed_files = set()

    # Get initially existing files
    for file_path in inbox_path.glob("*"):
        if file_path.is_file():
            processed_files.add(file_path.name)

    print(f"Initial files in inbox: {list(processed_files)}")
    print("Monitoring for new files. Press Ctrl+C to stop.\n")

    try:
        while True:
            # Check for new files
            current_files = set()
            for file_path in inbox_path.glob("*"):
                if file_path.is_file():
                    current_files.add(file_path.name)

            # Find new files
            new_files = current_files - processed_files

            for new_file in new_files:
                file_path = inbox_path / new_file
                print(f"🔍 Detected new file: {new_file}")

                # Call the AI Employee's file processing directly
                print(f"📦 Processing file: {new_file}")
                ai_employee._process_new_file(file_path)
                print(f"✅ Finished processing: {new_file}")

                # Update processed files set
                processed_files.add(new_file)

            time.sleep(1)  # Check every second

    except KeyboardInterrupt:
        print("\n🛑 Stopping file monitor...")

if __name__ == "__main__":
    simple_monitor()