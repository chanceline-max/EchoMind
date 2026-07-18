## Summary

Describe the problem, the smallest implemented change, and anything deliberately left out.

## Verification

List every command run and its result, including failures and subsequent fixes.

## Checklist

- [ ] The change has a clear, scoped purpose and does not include unrelated refactoring.
- [ ] Relevant tests pass; full regression was run when the user-facing flow changed.
- [ ] Ruff/format/mypy or ESLint/TypeScript/build checks pass as applicable.
- [ ] No real chat, Profile, database, `.env`, API key, token, local path, or sensitive snapshot is included.
- [ ] Historical Alembic migrations were not modified.
- [ ] Any new migration passed upgrade → downgrade → upgrade and metadata drift tests.
- [ ] Privacy, logging, cache, temporary-file, and remote-network impacts are documented.
- [ ] Remote network behavior remains explicit, bounded, and disabled by default.
- [ ] Evidence traceability and the separation of Insight status from confidence are preserved.
- [ ] Human review is not bypassed and Profile inclusion semantics remain explicit.
- [ ] ProfileSnapshot/InsightRevision immutability and deletion constraints are preserved.
- [ ] Documentation and release notes were updated when contracts or privacy boundaries changed.
- [ ] Screenshots, fixtures, and examples contain synthetic data only.

## Evidence and privacy impact

Explain changes to Evidence, Confidence, Review, Profile, storage, logs, exports, Provider payloads, or browser persistence. Write “none” only after checking each relevant boundary.

## Known limitations

List unresolved risks or follow-up work without presenting it as already scheduled.
