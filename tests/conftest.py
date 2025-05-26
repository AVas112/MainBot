import sys
import os

# Add the project root directory to the Python path
# This allows pytest to find the 'src' module
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# This file is intentionally left empty for now beyond path setup.
# It serves as a marker for pytest to discover tests in this directory
# and allows for project-specific configurations and fixtures.
