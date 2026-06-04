from __future__ import annotations

from benchmark.static_security_bench import run_static_security_benchmark


def test_static_security_benchmark_has_no_regressions() -> None:
    result = run_static_security_benchmark()

    assert result.failures == []
    assert result.precision == 100.0
    assert result.recall == 100.0
