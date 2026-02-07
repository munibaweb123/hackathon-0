#!/usr/bin/env python3
"""
Direct runner script for the Silver Tier Agent that handles import issues
"""

import sys
import os
from pathlib import Path
import importlib.util

def run_silver_tier():
    # Get the project root
    project_root = Path(__file__).parent
    agent_skills_dir = project_root / "agent-skills"

    # Add the project root and agent-skills to the Python path
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(agent_skills_dir))

    # Add all subdirectories to the path to allow direct imports
    subdirs = ["core", "watchers", "skills", "mcp_server", "scheduler", "models"]
    for subdir in subdirs:
        subdir_path = agent_skills_dir / subdir
        if subdir_path.exists():
            sys.path.insert(0, str(subdir_path))

    # Now we need to dynamically load and run the main module
    main_py_path = agent_skills_dir / "cli" / "main.py"

    # Read and execute the main.py file directly
    with open(main_py_path, 'r') as f:
        main_code = f.read()

    # Create a namespace for execution
    main_globals = {
        '__name__': '__main__',
        '__file__': str(main_py_path),
        'sys': sys,
        'os': os,
        'Path': Path,
        'importlib': importlib,
    }

    # Execute the main module code
    exec(main_code, main_globals)

    # If the main module has a main function, call it with the current command line args
    if 'main' in main_globals:
        # Set the command line arguments
        original_argv = sys.argv
        try:
            sys.argv = original_argv  # Pass through the actual command line args
            main_globals['main']()
        finally:
            sys.argv = original_argv

if __name__ == "__main__":
    run_silver_tier()