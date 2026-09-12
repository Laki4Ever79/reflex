# Convex — the durable record

`state.json` is the working copy and it does not survive a Render deploy.
Convex holds every routing decision permanently: what was corrected, which lane
it went to, the allocator's reasoning, and what the context tax was at that
moment.

Writes are fire-and-forget from `allocator/convex_store.py` — if Convex is
unreachable the demo is unaffected, it just loses the archive for those rows.

## Setup

```bash
npx convex dev            # authenticates, creates the deployment, pushes schema
```

Then put the deployment URL in the environment (locally and on Render):

```
CONVEX_URL=https://<your-deployment>.convex.cloud
```
