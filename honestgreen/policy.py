"""Team policy, read from .honestgreen.toml (stdlib tomllib, no dependencies)."""
from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from honestgreen.model import SEVERITIES
from honestgreen.parsers import DEFAULT_TEST_PATTERNS
from honestgreen.values import DEFAULT_SPEC_PATTERNS

POLICY_FILE = ".honestgreen.toml"

DEFAULT_POLICY = """\
# Honest Green policy
version = 1

# Severity that fails the check: "high", "medium", "low" or "never"
fail_on = "high"

# Tests matching these globs are protected: any change to them is reported
# as high severity and needs a justification.
protected = [
  # "src/test/java/**/payment/**",
  # "tests/critical/**",
]

# Extra globs for files that contain tests (defaults cover pytest and JUnit layouts)
# test_patterns = ["it/**/*.py"]

# Files that hold the specification (business rules, API contracts). Production
# values that contradict them are reported (HG020). Defaults: README.md, SPEC.md,
# docs/**/*.md, spec(s)/**/*.md, requirements/**/*.md, OpenAPI/Swagger files.
# spec = ["README.md", "docs/rules/**/*.md"]

# Per-detector overrides
# [detectors.HG003]
# severity = "high"
# [detectors.HG004]
# enabled = false
"""


class PolicyError(ValueError):
    pass


@dataclass
class Policy:
    fail_on: str = "high"
    protected: list[str] = field(default_factory=list)
    test_patterns: tuple[str, ...] = DEFAULT_TEST_PATTERNS
    spec_patterns: tuple[str, ...] = DEFAULT_SPEC_PATTERNS
    detectors: dict = field(default_factory=dict)

    def is_protected(self, path: str) -> bool:
        return any(fnmatch.fnmatch(path, pat) for pat in self.protected)

    def enabled(self, detector: str) -> bool:
        return self.detectors.get(detector, {}).get("enabled", True)

    def severity_for(self, detector: str, default: str) -> str:
        return self.detectors.get(detector, {}).get("severity", default)


def load(path: Path) -> Policy:
    if not path.exists():
        raise PolicyError(f"{path}: file not found")
    return from_text(path.read_text(), str(path))


def from_text(text: str | None, origin: str = POLICY_FILE) -> Policy:
    """Parse a policy. None (no policy file) gives the defaults."""
    if text is None:
        return Policy()
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise PolicyError(f"{origin}: {e}") from e
    fail_on = data.get("fail_on", "high")
    if fail_on not in (*SEVERITIES, "never"):
        raise PolicyError(f"fail_on must be one of {', '.join(SEVERITIES)}, never")
    for det, conf in data.get("detectors", {}).items():
        if "severity" in conf and conf["severity"] not in SEVERITIES:
            raise PolicyError(f"detectors.{det}.severity must be one of {', '.join(SEVERITIES)}")
    return Policy(
        fail_on=fail_on,
        protected=list(data.get("protected", [])),
        test_patterns=DEFAULT_TEST_PATTERNS + tuple(data.get("test_patterns", [])),
        spec_patterns=tuple(data["spec"]) if "spec" in data else DEFAULT_SPEC_PATTERNS,
        detectors=data.get("detectors", {}),
    )
