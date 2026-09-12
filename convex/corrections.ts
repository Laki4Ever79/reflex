import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

/** Append one routing decision. Idempotent on correctionId so a replay of the
 *  local state after a redeploy does not duplicate history. */
export const record = mutation({
  args: {
    correctionId: v.number(),
    ts: v.string(),
    agentSaid: v.string(),
    userWanted: v.string(),
    situation: v.string(),
    cluster: v.string(),
    recurrence: v.number(),
    lane: v.string(),
    rationale: v.string(),
    confidence: v.number(),
    artifact: v.any(),
    contextTokens: v.number(),
    ifAllContext: v.number(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("corrections")
      .withIndex("by_correction", (q) => q.eq("correctionId", args.correctionId))
      .first();
    if (existing) return existing._id;
    return await ctx.db.insert("corrections", args);
  },
});

/** Everything ever routed, newest first. Survives deploys; state.json does not. */
export const history = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, { limit }) =>
    await ctx.db.query("corrections").order("desc").take(limit ?? 100),
});

/** How the lanes have split across all time, not just since the last deploy. */
export const laneTotals = query({
  args: {},
  handler: async (ctx) => {
    const rows = await ctx.db.query("corrections").collect();
    const t: Record<string, number> = { code: 0, weights: 0, context: 0 };
    for (const r of rows) if (r.lane in t) t[r.lane]++;
    return { ...t, total: rows.length };
  },
});
