"""
Bridge so drone/ can write to the same telemetry snapshot that
vision/ reads from, without drone/ depending on vision/'s package
layout directly. Keeps the two folders loosely coupled per the
review's "don't mix modules together" guidance.

telemetry_snapshot.py itself has zero cross-file dependencies (just
stdlib), so it's safe to import via a direct sys.path insertion here
rather than needing the full `vision.detectors.telemetry_snapshot`
package path -- this keeps drone/ runnable standalone without also
needing to run everything via `python -m` from the project root.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "vision" / "detectors"))
from telemetry_snapshot import write_snapshot, get_current_position  # noqa: E402,F401
