#!/usr/bin/env python3
"""
Runner script for the Silver Tier Agent
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Temporarily add the project root to sys.modules to allow dotted imports
if str(project_root) not in [os.path.dirname(p) for p in sys.path if isinstance(p, str)]:
    sys.path.insert(0, str(project_root))

# Create a temporary alias for the agent-skills directory
agent_skills_path = project_root / "agent-skills"
if str(agent_skills_path) not in sys.path:
    sys.path.insert(0, str(agent_skills_path))

# Add the individual subdirectories to the path to make imports work
for subdir in ["core", "watchers", "skills", "mcp_server", "scheduler", "models"]:
    subdir_path = agent_skills_path / subdir
    if subdir_path.exists() and str(subdir_path) not in sys.path:
        sys.path.insert(0, str(subdir_path))

# Import and run the Silver Tier agent
def main():
    from agent_skills.cli.main import main as agent_main
    import sys
    # Pass command line arguments to the actual main function
    sys.argv = sys.argv[:]  # Copy argv to make sure it's available
    agent_main()

if __name__ == "__main__":
    main()