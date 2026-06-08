/// <reference types="vitest/globals" />
// Makes vitest's global test APIs (describe/it/expect/beforeAll/afterEach/…)
// known to tsc and `next build`, matching `globals: true` in vitest.config.ts.
// Without this, typecheck/build fail on the *.test.ts(x) files even though
// vitest injects these globals at runtime.
