# docs/

Agent-maintained notes for this repository. The owner rarely reads these, so they exist for
the next agent: what was investigated, what is known, what is still a guess, and why the config
looks the way it does.

**Rules for agents** (also stated in `/CLAUDE.md`):
- Read the relevant note here before working on a topic; add a new note when you start one.
- Update notes as part of the same change that alters behaviour or learns something new.
- Separate **verified** facts (with date and how checked) from **hypotheses**. Never leave a
  hypothesis reading like a fact.
- Date every live-instance observation. Entity states go stale quickly.
- Keep notes short and concrete. One topic per file, linked from the index below.
- Never put tokens or secrets in here (`gitsync.sh` commits everything under `/config`).

## Index

| Note | Topic |
|---|---|
| [trv-radiators-stay-hot.md](trv-radiators-stay-hot.md) | Radiators hot with the valve "closed": sync gap vs TRVZB calibration drift |
| [heating-control-state-machines.md](heating-control-state-machines.md) | Away-mode restart bug (verified), the competing heating writers, and a proposal to unify them |
