# API Client Structure

`lib/api/client.ts` — fetch wrapper (base URL, auth header injection, retry/backoff, RFC7807 parsing). `lib/query/keys.ts` — typed hierarchical key factory. Types generated from backend OpenAPI (openapi-typescript). Zod validates at runtime boundaries. Mutations use useMutation with optimistic update + invalidate-by-prefix.
