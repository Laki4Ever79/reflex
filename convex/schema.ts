import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

// Render's filesystem is ephemeral: every deploy resets state.json to the seed.
// Convex is the only thing here that outlives a deploy, so it holds the durable
// record of what the allocator decided and why.
export default defineSchema({
  corrections: defineTable({
    correctionId: v.number(),
    ts: v.string(),
    agentSaid: v.string(),
    userWanted: v.string(),
    situation: v.string(),
    cluster: v.string(),
    recurrence: v.number(),
    lane: v.string(),          // code | weights | context
    rationale: v.string(),
    confidence: v.number(),
    artifact: v.any(),
    contextTokens: v.number(), // carried on every call, at the time of this decision
    ifAllContext: v.number(),  // what a one-lane agent would have been carrying
  })
    .index("by_correction", ["correctionId"])
    .index("by_lane", ["lane"])
    .index("by_cluster", ["cluster"]),
});
