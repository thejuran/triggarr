// Triggarr-only agent.spawn hook: routes a bm:bm-plan-checker spawn to the
// model-gateway Codex model so the plan checker runs on Codex while the
// orchestrating session stays on Anthropic.
//
// No try/catch wraps the next() call on purpose: an unavailable model, an
// unreachable gateway, a timeout, or an incomplete response must surface as
// a visible error, never a silent fallback to a Claude model. The handler
// only ever changes `model` on the spawn event; every other field passes
// through unchanged. Re-verify this model id against the model-gateway
// catalog (`model-gateway.js doctor`) after any gateway update.
export function register(on) {
  on('agent.spawn', { subagentType: 'bm:bm-plan-checker' }, async ($, e, next) =>
    next({ ...e, model: 'claude-gpt-6-astra[1m]' })
  );
}
