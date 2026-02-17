#!/usr/bin/env python3
"""Log test failure information to a timestamped file."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def log_test_failure(
    test_name: str,
    likely_cause: str,
    stack_trace: str,
    additional_context: Optional[dict] = None,
    output_dir: str = "tmp",
) -> Path:
    """Log a test failure to a timestamped JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_test_name = (
        test_name.replace("::", "_").replace("/", "_").replace(".", "_")[:50]
    )
    filename = f"test_failure_{timestamp}_{safe_test_name}.json"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    failure_data = {
        "test_name": test_name,
        "timestamp": datetime.now().isoformat(),
        "likely_cause": likely_cause,
        "stack_trace": stack_trace,
        "additional_context": additional_context or {},
    }

    filepath = output_path / filename
    with open(filepath, "w") as f:
        json.dump(failure_data, f, indent=2)

    print(f"✓ Test failure logged to: {filepath}")
    return filepath


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print(
            "Usage: python log_test_failure.py <test_name> <likely_cause> <stack_trace> [output_dir]"
        )
        sys.exit(1)

    log_test_failure(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        output_dir=sys.argv[4] if len(sys.argv) > 4 else "tmp",
    )
