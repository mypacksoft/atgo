<!-- Tell the reviewer the WHY first, then the WHAT. -->

## Summary



## Changes

-

## Test plan

- [ ]
- [ ]

## Risk / blast radius

<!-- One line: what's the worst-case if this is wrong? Tenant data leak? Service outage? Cosmetic? -->

## Checklist

- [ ] Touched code has type hints (Python) / strict TS (frontend)
- [ ] No new SQL string concatenation with user input
- [ ] If touching tenant-scoped tables: RLS still applies
- [ ] If touching ADMS receiver: tested with `scripts/simulate_zkteco.py`
- [ ] If touching billing: verified webhook signature handling
- [ ] No secrets / personal info in diff
