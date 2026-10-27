// Classic PreToolUse guard: refuses a bm:bm-plan-checker Agent spawn whenever
// the agent.spawn module hook that would route it to the Codex backend has
// not loaded (CLAUDE_CODE_ENABLE_FUNCTION_HOOKS is not "1"). Classic hooks
// load even when the modules gate is off, so this is the fail-closed
// backstop for register.js: it can only block a spawn, never allow or
// rewrite one. Prints only the flag state on refusal, never env contents.
let raw = '';
process.stdin.on('data', (chunk) => {
  raw += chunk;
});
process.stdin.on('error', () => {
  // Stream-level error (broken pipe, ECONNRESET, etc.) -- fail closed rather than
  // let Node's uncaught-exception path pick an exit code outside this script's
  // deliberate contract (0 or 2).
  process.stderr.write(
    'planchk-router: stdin error while reading PreToolUse input; refusing Agent spawn so the Codex route cannot silently fail. Stop and report.\n'
  );
  process.exitCode = 2;
});
process.stdin.on('end', () => {
  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    process.stderr.write(
      'planchk-router: could not parse PreToolUse input; refusing Agent spawn so the Codex route cannot silently fail. Stop and report.\n'
    );
    // Set exitCode (not process.exit()) so the write above is guaranteed to flush
    // before the process ends naturally -- process.exit() right after a stderr
    // write can truncate the message on a piped stream.
    process.exitCode = 2;
    return;
  }

  const toolInput = input && input.tool_input;
  if (!toolInput || toolInput.subagent_type !== 'bm:bm-plan-checker') {
    process.exit(0);
    return;
  }

  if (process.env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS === '1') {
    process.exit(0);
    return;
  }

  process.stderr.write(
    'planchk-router: refusing bm:bm-plan-checker spawn - CLAUDE_CODE_ENABLE_FUNCTION_HOOKS is not 1, so the Codex route would silently not apply. Stop and report.\n'
  );
  // Same reasoning as above: exitCode, not process.exit(), so the write flushes.
  process.exitCode = 2;
});
