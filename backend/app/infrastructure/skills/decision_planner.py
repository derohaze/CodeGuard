from __future__ import annotations

import re
from typing import Optional

from app.infrastructure.skills.registry import SkillRegistry


SKILL_KEYWORDS: dict[str, list[str]] = {
    "recon": ["recon", "subdomain", "subdomains", "enumerate", "enumeration", "attack surface",
              "crt", "liveness", "fingerprint", "fingerprinting", "content discovery", "apex", "domain"],
    "webvuln": ["web", "vuln", "vulnerability", "hunt", "idor", "bola", "bac", "xss", "sqli",
                "injection", "auth", "authorization", "ssrf", "cve", "api", "endpoint"],
    "jwt": ["jwt", "token", "bearer", "alg", "kid", "jku", "jwks", "hs256", "rs256"],
    "ssrf": ["ssrf", "webhook", "callback", "url", "metadata", "169.254.169.254", "imds"],
    "ssti": ["ssti", "template", "jinja", "twig", "freemarker", "velocity", "handlebars"],
    "graphql": ["graphql", "gql", "introspection", "query", "mutation", "alias", "schema"],
    "race": ["race", "concurrent", "parallel", "coupon", "redeem", "balance", "double spend"],
    "takeover": ["takeover", "dangling", "cname", "nxdomain", "subdomain takeover"],
    "supabase": ["supabase", "rls", "anon key", "postgrest", "storage bucket"],
    "deserialize": ["deserialize", "deserialization", "pickle", "unserialize", "binaryformatter", "yaml"],
}

HIGH_RISK_TERMS = ["exploit", "rce", "sqlmap", "nuclei", "ffuf", "masscan", "bruteforce",
                   "brute force", "delete", "dos", "ddos", "fuzz"]

WORKFLOW_TERMS = ["test", "scan", "recon", "enumerate", "hunt", "check", "verify",
                  "exploit", "poc", "bug", "vuln", "vulnerability", "endpoint", "api",
                  "auth", "authorization", "finding"]


class DecisionPlan:
    def __init__(
        self,
        recommended_skill: Optional[str] = None,
        reason: str = "",
        risk: str = "normal",
        checklist: Optional[list[str]] = None,
        guidance: str = "",
    ):
        self.recommended_skill = recommended_skill
        self.reason = reason
        self.risk = risk
        self.checklist = checklist or []
        self.guidance = guidance


def build_decision_plan(
    user_message: str,
    skill_registry: SkillRegistry,
    target_url: str = "",
) -> Optional[DecisionPlan]:
    text = user_message.strip()
    if not text:
        return None

    normalized = text.lower().replace("-", " ").replace("_", " ")
    recommended = _recommend_skill(normalized, skill_registry)
    risk = "high" if any(t in normalized for t in HIGH_RISK_TERMS) else "normal"
    target_known = bool(target_url) or bool(re.search(r'https?://\S+', text)) or \
        bool(re.search(r'\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b', text, re.I))

    if not recommended and risk == "normal" and not target_known and \
       not any(t in normalized for t in WORKFLOW_TERMS):
        return None

    checklist = _build_checklist(recommended, target_known, risk)
    reason = recommended or "no specialized skill matched strongly"
    guidance = _render_guidance(recommended, reason, risk, checklist)

    return DecisionPlan(
        recommended_skill=recommended,
        reason=reason,
        risk=risk,
        checklist=checklist,
        guidance=guidance,
    )


def _recommend_skill(normalized: str, registry: SkillRegistry) -> Optional[str]:
    best_score = 0
    best_name: Optional[str] = None
    for skill in registry.list_enabled():
        score = 0
        keywords = SKILL_KEYWORDS.get(skill.name, []) + [skill.name]
        for kw in keywords:
            if kw.lower() in normalized:
                score += 1
        if score > best_score:
            best_score = score
            best_name = skill.name
    return best_name


def _build_checklist(skill_name: Optional[str], target_known: bool, risk: str) -> list[str]:
    out: list[str] = []
    if not target_known:
        out.append("clarify the exact in-scope target before active testing")
    if skill_name:
        out.append(f"load the {skill_name} skill before running other tools")
    else:
        out.append("choose the narrowest applicable workflow before acting")
    out.append("verify with reproducible evidence before confirming a finding")
    if risk == "high":
        out.append("ask before scanner-like, destructive, or high-volume actions")
    return out


def _render_guidance(skill_name: Optional[str], reason: str, risk: str, checklist: list[str]) -> str:
    skill_line = f"Recommended skill: {skill_name} ({reason})." if skill_name else f"Recommended skill: none ({reason})."
    lines = [
        "Decision planner guidance:",
        f"- {skill_line}",
        f"- Risk level: {risk}.",
    ]
    if skill_name:
        lines.append("- Call load_skill before other tools.")
    lines.append("- Checklist:")
    for item in checklist:
        lines.append(f"  - {item}")
    return "\n".join(lines)
