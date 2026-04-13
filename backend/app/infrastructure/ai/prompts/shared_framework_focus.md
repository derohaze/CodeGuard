Framework-specific focus modules:

- GraphQL:
  - treat schema, query, mutation, resolver, args, variables, input objects, and context/session objects as first-class sources
  - watch auth directives, middleware, resolver-layer policy checks, raw SQL/raw query APIs, file import paths, and command helpers
  - distinguish schema exposure issues from execution-path issues
- FastAPI / Python web services:
  - treat request bodies, query/path params, headers, cookies, dependency-injected auth/session context, and file helpers as high-signal inputs
  - prefer sink-level fixes over route-only checks when the vulnerable operation is deeper in the service layer
- Java servlet / JAX-RS / JSP:
  - treat request parameter/header/cookie/session access, RequestDispatcher forward/include, sendRedirect, JDBC execution, and session/auth transitions as high-signal markers
  - distinguish controller/view wiring from service, DAO, repository, and auth/session enforcement
- Multi-service / gRPC / outbound calls:
  - use service edges, grpc/http clients, and service-address markers conservatively
  - identify supported trust-boundary hops, not speculative distributed chains
- When the framework is ambiguous:
  - remain conservative
  - disclose ambiguity
  - avoid over-specialized claims
