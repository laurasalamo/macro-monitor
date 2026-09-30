"""Make the flat-imported modules in scripts/ importable from the tests."""

import os
import sys

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
