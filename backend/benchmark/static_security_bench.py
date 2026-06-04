from __future__ import annotations

"""Deterministic static detector benchmark for Aegix.

This benchmark intentionally avoids AI providers so false-positive and
false-negative changes in local detectors are measurable in CI and during
development.

Usage:
    cd backend
    python benchmark/static_security_bench.py
"""

import json
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.services.repository.codeql_lite import build_program_database, run_codeql_lite_queries
from app.infrastructure.services.repository.repository_analysis import run_precise_heuristics


@dataclass(frozen=True, slots=True)
class StaticBenchmarkCase:
    id: str
    language: str
    filename: str
    content: str
    expected_category: str | None


@dataclass(frozen=True, slots=True)
class StaticBenchmarkResult:
    cases: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    failures: list[dict]


STATIC_BENCHMARK_CASES: tuple[StaticBenchmarkCase, ...] = (
    StaticBenchmarkCase(
        id="python_mongo_public_key_operator_injection",
        language="python",
        filename="security_repository.py",
        expected_category="NoSQL injection",
        content="""
class SecurityRepository:
    def get_by_public_key_for_user(self, user_id: str, public_key: dict):
        return self.collection.find_one({
            "user_id": user_id,
            "device_public_key": public_key,
        })
""".strip(),
    ),
    StaticBenchmarkCase(
        id="python_mongo_escaped_regex_is_not_operator_injection",
        language="python",
        filename="catalog_repository.py",
        expected_category=None,
        content="""
import re

class CatalogRepository:
    def search_products(self, search: str):
        query = {
            "$or": [
                {"name": {"$regex": re.escape(search), "$options": "i"}},
                {"sku": {"$regex": re.escape(search), "$options": "i"}},
            ]
        }
        return list(self.collection.find(query))
""".strip(),
    ),
    StaticBenchmarkCase(
        id="python_mongo_update_set_is_not_filter_injection",
        language="python",
        filename="woocommerce_sync.py",
        expected_category=None,
        content="""
class WooSyncStatusRepository:
    def update_status(self, sync_id: str, fields: dict[str, str]):
        return self.collection.update_one({"id": sync_id}, {"$set": fields})
""".strip(),
    ),
    StaticBenchmarkCase(
        id="python_mongo_update_payload_is_not_filter_injection",
        language="python",
        filename="sync_payload.py",
        expected_category=None,
        content="""
def update_status(fields):
    return statuses.update_one({"id": "fixed"}, {"$set": fields})
""".strip(),
    ),
    StaticBenchmarkCase(
        id="node_mongo_raw_body_filter",
        language="javascript",
        filename="auth.js",
        expected_category="NoSQL injection",
        content="""
app.post("/login", async (req, res) => {
  const user = await User.findOne(req.body);
  res.json({ id: user?._id });
});
""".strip(),
    ),
    StaticBenchmarkCase(
        id="node_mongo_scalar_string_cast",
        language="javascript",
        filename="customers.js",
        expected_category=None,
        content="""
app.get("/customers", async (req, res) => {
  const user = await User.findOne({ email: String(req.query.email) });
  res.json({ id: user?._id });
});
""".strip(),
    ),
    StaticBenchmarkCase(
        id="rust_sqlx_format_query",
        language="rust",
        filename="users.rs",
        expected_category="SQL injection",
        content=r'''
async fn search_users(Query(params): Query<SearchParams>, pool: PgPool) {
    let query = format!("SELECT * FROM users WHERE name LIKE '%{}%'", params.search);
    let rows = sqlx::query(&query).fetch_all(&pool).await.unwrap();
}
'''.strip(),
    ),
    StaticBenchmarkCase(
        id="rust_sqlx_bind_query",
        language="rust",
        filename="users_safe.rs",
        expected_category=None,
        content=r'''
async fn get_user(Path(user_id): Path<i64>, pool: PgPool) {
    let row = sqlx::query("SELECT * FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_one(&pool)
        .await
        .unwrap();
}
'''.strip(),
    ),
)


def run_static_security_benchmark() -> StaticBenchmarkResult:
    true_positives = 0
    true_negatives = 0
    false_positives = 0
    false_negatives = 0
    failures: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="aegix-static-bench-") as tmp:
        source_root = Path(tmp)
        for case in STATIC_BENCHMARK_CASES:
            case_path = source_root / case.language / case.filename
            case_path.parent.mkdir(parents=True, exist_ok=True)
            case_path.write_text(case.content, encoding="utf-8")

            findings = run_precise_heuristics(case_path, case.content, source_root)
            if case.filename.endswith(".py"):
                program = build_program_database(source_root, [case_path])
                findings.extend(run_codeql_lite_queries(program))
            categories = {str(item.get("category", "")) for item in findings}
            matched = case.expected_category in categories if case.expected_category else not categories

            if case.expected_category and matched:
                true_positives += 1
            elif case.expected_category and not matched:
                false_negatives += 1
                failures.append(_failure(case, findings))
            elif case.expected_category is None and matched:
                true_negatives += 1
            else:
                false_positives += 1
                failures.append(_failure(case, findings))

    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    precision = true_positives / precision_denominator if precision_denominator else 1.0
    recall = true_positives / recall_denominator if recall_denominator else 1.0
    return StaticBenchmarkResult(
        cases=len(STATIC_BENCHMARK_CASES),
        true_positives=true_positives,
        true_negatives=true_negatives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=round(precision * 100, 1),
        recall=round(recall * 100, 1),
        failures=failures,
    )


def _failure(case: StaticBenchmarkCase, findings: list[dict]) -> dict:
    return {
        "id": case.id,
        "language": case.language,
        "expected_category": case.expected_category,
        "actual_categories": [str(item.get("category", "")) for item in findings],
        "actual_titles": [str(item.get("title", "")) for item in findings],
    }


def main() -> int:
    result = run_static_security_benchmark()
    payload = asdict(result)
    report_path = Path(__file__).resolve().parent.parent / "artifacts" / "static-security-benchmark.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
