Use AIDesigner for the request in $ARGUMENTS.

Workflow:
1. Gather design context before spending credits:
   - Read `DESIGN.md`, `.aidesigner/DESIGN.md`, or `docs/design.md` if present
   - Inspect theme files, tokens, fonts, shared components, and the target route/page
2. Write a compact internal design brief from that repo context:
   - platform and surface
   - product goal and main user action
   - visual language to preserve, evolve, or reset
   - important repo patterns, constraints, and content types
   - concrete typography/tokens only if preserving the current repo aesthetic
3. Split the task into:
   - a visual reference prompt for AIDesigner
   - a detailed implementation spec you keep local
4. Rewrite $ARGUMENTS into a broad visual reference prompt before calling AIDesigner.
   - Focus on product type, audience, UX priorities, overall feel, and non-negotiable constraints.
   - Let AIDesigner choose the specific layout, supporting sections, composition, and most stylistic details.
   - Avoid exact section orders, card counts, micro-copy, and detailed per-element placement unless the user explicitly requested them.
   - Do not pass exhaustive content outlines, tables, command lists, API fields, or other documentation detail dumps into the prompt.
   - If the user gave a very specific page spec, compress it into a smaller visual brief for AIDesigner and save the full spec for local implementation.
   - If matching an existing aesthetic, it is fine to mention concrete repo colors, fonts, and tokens.
   - If this is a new design or revamp, keep styling guidance broad and do not hard-code exact colors or gradients unless the user explicitly asked for them.
5. Prefer the connected `aidesigner` MCP server for `whoami`, `get_credit_status`, `generate_design`, and `refine_design`.
   - Keep calls prompt-driven unless the user explicitly asked for a reference-URL workflow.
   - Use `mode: "clone"` only for a near-1:1 recreation or faithful copy of a specific URL.
   - Use `mode: "enhance"` only to improve or modernize a specific URL while preserving its content or intent.
   - Use `mode: "inspire"` only for a new design inspired by a specific URL or its visual style.
   - If the user only mentions a URL as context, do not pass `mode` or `url`.
   - If the user wants one of those reference workflows but has not provided the URL yet, stop and ask for it before spending credits.
   - If a prior run already used a reference mode and the user still wants that workflow, use `refine_design` and keep the same `mode` and `url`.
   - If the user explicitly wants to move away from the reference, drop `mode` and `url` and continue prompt-only. Refine from the latest HTML artifact instead of a prior run id if you need to avoid inheriting the old reference mode.
6. After a successful MCP generation or refinement, persist the returned HTML into a local run:
   - Prefer piping the HTML into `npx -y @aidesigner/agent-skills capture --prompt "<final prompt>" --transport mcp --remote-run-id "<run-id>"`
   - If piping is awkward, write the HTML to `.aidesigner/mcp-latest.html` and run `npx -y @aidesigner/agent-skills capture --html-file .aidesigner/mcp-latest.html --prompt "<final prompt>" --transport mcp --remote-run-id "<run-id>"`
7. If MCP is unavailable or needs re-auth:
   - If `AIDESIGNER_API_KEY` is already set, use `npx -y @aidesigner/agent-skills generate --prompt "<final prompt>"`
   - Otherwise stop and show setup instructions:
     - Recommended: `npx -y @aidesigner/agent-skills init`, then open Claude Code, run `/mcp`, and sign into `aidesigner`
     - Cross-repo: `npx -y @aidesigner/agent-skills init --scope user`
     - Fallback: set `AIDESIGNER_API_KEY` and retry
8. After every successful run, use the preview image and run `npx -y @aidesigner/agent-skills adopt --id <run-id>`.
9. Treat HTML as a design artifact first and implementation input second.
10. The design artifact defines two distinct layers - port them differently:
    - Design system layer (match precisely): extract and faithfully reproduce every visual decision from the artifact - palette, gradients, shadows, radii, border styles, spacing, typography values, background effects, opacity, transitions, and layout structure. Convert them into the repo's native token system rather than approximating with "close enough" utility classes. When the artifact defines exact values, those are the spec.
    - Content layer (adapt freely): copy, section count, placeholder data, button labels, testimonial quotes, logo names, and other content should come from the user's actual product context and request unless they explicitly asked for a close recreation.
11. When porting the design system layer, work methodically:
    - First extract theme tokens from the artifact config/styles and define them in the repo token system.
    - Then port each component's visual structure, preserving exact spacing, sizing, and effects.
    - Do not substitute approximate values such as `pt-48` for `pt-32`, `min-h-screen` for `min-h-[90vh]`, or `text-6xl` for `text-[64px]`.
12. Apply the full user requirements during repo implementation using local content, behaviors, and component structure. Do not ship raw standalone HTML into app code.
