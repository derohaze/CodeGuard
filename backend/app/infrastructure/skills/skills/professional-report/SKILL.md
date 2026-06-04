---
name: professional-report
description: Industry-standard penetration test report format. Load this skill before generating the final report to ensure output follows professional security assessment standards (compatible with PTES, OWASP testing guide, and Bugcrowd VRT).
allowed-tools:
  - file_write
  - confirm_finding
---

# Professional pentest report format

Generate the final report as a structured penetration test report following industry standards. The report must be complete, evidence-driven, and actionable.

## Report structure

### 1. Executive Summary (2-3 paragraphs)

- **Engagement scope**: what was tested (target URLs, endpoints, testing window)
- **Overall risk rating**: Critical / High / Medium / Low based on findings
- **High-level summary**: 2-3 sentences on what was found and the biggest risk
- **Bottom line**: one sentence business-impact statement

### 2. Scope and Methodology

- **In-scope**: List of all tested endpoints, services, authentication levels
- **Testing methodology**: OWASP WSTG, PTES, custom methodology
- **Tools used**: curl, custom HTTP tool, web search, source code review
- **Access level**: Black box / Grey box / White box (state clearly)

### 3. Finding Summary Table

| # | Finding | Severity | Endpoint | Status |
|---|---|---|---|---|
| 1 | SQL Injection in login | Critical | POST /api/auth/login | Confirmed |
| 2 | IDOR in user profile | High | GET /api/users/{id} | Confirmed |

### 4. Detailed Findings

For EACH finding:

```
## F-001: [Title]

**Severity**: Critical / High / Medium / Low / Info
**Category**: e.g., Injection, Broken Access Control, XSS
**Endpoint**: Full URL + method
**CVSS-like score**: N/A or estimated

### Description
Brief technical description of the vulnerability.

### Steps to Reproduce
1. Step-by-step
2. With exact curl commands
3. And expected vs actual responses

### Proof of Concept (raw evidence)
```
Request:
GET /api/users/1 HTTP/1.1
Host: 127.0.0.1:8000
Authorization: Bearer <token_b>

Response:
HTTP/1.1 200 OK
{"id":1,"email":"admin@example.com","role":"admin"}
```

### Impact
What an attacker can actually achieve by exploiting this finding.

### Remediation
Concrete fix recommendation. Reference code patterns if available.
```

### 5. Attack Chains

For each multi-step attack chain that was validated:

```
### Chain 1: [Name]
Step 1: [finding ref] → [outcome]
Step 2: [finding ref] → [outcome]
Final: [business impact]
```

### 6. Coverage Summary

| Area | Status | Notes |
|---|---|---|
| Authentication | Tested | 3 endpoints tested |
| Authorization | Partial | Missing admin role tests |
| Input Validation | Tested | 5 injection vectors tested |
| Business Logic | Not tested | Requires authenticated sessions |

### 7. Analysis Limitations

- What was NOT tested (and why)
- What assumptions were made
- What would improve confidence

### 8. Recommendations (prioritized)

1. **Critical**: Fix SQL injection in login — immediate action required
2. **High**: Implement proper access controls for user profile endpoint
3. **Medium**: Add input validation to search endpoint
4. **Low**: Rate limiting on login endpoint

## Output format

When writing the final report, use `file_write` to save it to `reports/pentest-report-YYYY-MM-DD.md`.

Before calling the report complete, verify:
- [ ] Every finding has a reproduction step with exact curl command
- [ ] Every finding has a response excerpt proving the bug
- [ ] Severity ratings follow OWASP / industry standards
- [ ] No generic or templated language — everything is target-specific
- [ ] Coverage shows what was and was not tested
