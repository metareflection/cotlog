"""E-prover subprocess wrapper."""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProverResult:
    szs_status: str  # Raw SZS status string
    label: str  # "True", "False", or "Uncertain"
    stdout: str
    stderr: str


_SZS_RE = re.compile(r'# SZS status (\w+)')


def run_eprover(tptp_content: str, cpu_limit: int = 30) -> ProverResult:
    """Run E-prover on TPTP content and parse the result."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.p', delete=False) as f:
        f.write(tptp_content)
        tptp_path = Path(f.name)

    try:
        result = subprocess.run(
            ['eprover', '--auto', '--tstp-format', f'--cpu-limit={cpu_limit}', str(tptp_path)],
            capture_output=True,
            text=True,
            timeout=cpu_limit + 10,
        )
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired:
        stdout = ''
        stderr = 'Process timed out'
    finally:
        tptp_path.unlink(missing_ok=True)

    szs_status = _parse_szs_status(stdout)
    label = _status_to_label(szs_status)
    return ProverResult(szs_status=szs_status, label=label, stdout=stdout, stderr=stderr)


def _parse_szs_status(stdout: str) -> str:
    m = _SZS_RE.search(stdout)
    return m.group(1) if m else 'Unknown'


def _status_to_label(status: str) -> str:
    if status == 'Theorem':
        return 'True'
    if status == 'CounterSatisfiable':
        return 'False'
    return 'Uncertain'


def prove_example(
    premises_tptp: list[str],
    conjecture_tptp: str,
    premises_ast: list,
    conjecture_ast,
    cpu_limit: int = 30,
) -> ProverResult:
    """Run the full proving strategy for a FOLIO example.

    Strategy:
    1. Try conjecture as-is. If Theorem → True.
    2. If not Theorem, negate conjecture and try again. If Theorem → False.
    3. Otherwise → Uncertain.
    """
    from .tptp import problem_to_tptp

    # Try conjecture as-is
    tptp = problem_to_tptp(premises_ast, conjecture_ast)
    result = run_eprover(tptp, cpu_limit)
    if result.szs_status == 'Theorem':
        return ProverResult('Theorem', 'True', result.stdout, result.stderr)

    # Try negated conjecture
    tptp_neg = problem_to_tptp(premises_ast, conjecture_ast, negate_conjecture=True)
    result_neg = run_eprover(tptp_neg, cpu_limit)
    if result_neg.szs_status == 'Theorem':
        return ProverResult('Theorem(negated)', 'False', result_neg.stdout, result_neg.stderr)

    # Neither provable
    return ProverResult(
        result.szs_status, 'Uncertain', result.stdout, result.stderr
    )
