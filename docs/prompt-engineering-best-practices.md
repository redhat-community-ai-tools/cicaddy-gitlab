# Prompt Engineering Best Practices for MCP Tool Integration

Patterns for structuring AI agent prompts with MCP tools, based on production experience.

## "Last Message Only" Architecture

The agent uses only the **last assistant message** as output. Earlier iterations (tool calls, partial analysis) are discarded from the final result.

```
Iteration 1: Library Detection → Tool Calls → Partial Analysis
Iteration 2: More Tool Calls → Additional Analysis
Iteration 3: Final Synthesis → LAST MESSAGE (this is what users see)
```

**Consequence**: Tool calls in early iterations won't appear in output unless the final message references them.

**Solution**: Invoke tools EARLY, synthesize results in the FINAL message.

## The 4-Step Pattern

Structure prompts so tools run before analysis:

```markdown
**1. Library Detection**
Scan diff for library imports in actual code (NOT in tests/comments/examples).

**2. Context7 Lookup** (if libraries found)
For each library: use "resolve-library-id" then "get-library-docs" (max 6 lookups).

**3. Review Structure**
- **Summary**: What changes accomplish
- **Issues**: Bugs, security, edge cases (cite library best practices if applicable)
- **Recommendations**: Actionable fixes with code examples
- **Code Quality**: Readability, maintainability

**4. Output**
Single comprehensive review. Markdown format. Specific line references. Concise and focused.
```

### Why Each Element Matters

| Element | Purpose |
|---------|---------|
| `(NOT in tests/comments/examples)` | Prevents wasting tool calls on libraries from test fixtures |
| `(max 6 lookups)` | Each lookup returns 5-15K tokens; limits prevent token exhaustion |
| `(cite library best practices if applicable)` | Forces AI to use fetched docs, not ignore them |
| `Single comprehensive review` | Prevents rambling multi-turn output |

## Key Principles

1. **Tools before analysis** — Tool calls must complete before the final synthesis step
2. **Numbered steps** — AI models follow numbered lists sequentially
3. **Explicit exclusions** — Define what to exclude, not just include
4. **Token-aware limits** — Cap tool calls to preserve budget for analysis
5. **Citation requirements** — Explicitly require use of tool results

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Tool calls after analysis | Final message lacks tool context | Move tool steps before analysis |
| No scope constraints | Wastes calls on test/comment libraries | Add `(NOT in tests/comments/examples)` |
| Unlimited tool calls | Exhausts token budget | Add `(max N lookups)` |
| Generic "use Context7" | AI doesn't know when/how to invoke | Use structured numbered workflow |
| No output constraints | Inconsistent format and length | Add explicit format/style requirements |

## Gemini: Preventing Silent Tool-Only Loops

Gemini sometimes returns responses with ONLY tool calls (no text), causing iteration loops where the same searches repeat until the limit.

### Solution: Mandatory Text with Tool Calls

```markdown
**EXECUTION WORKFLOW**:
1. FIRST RESPONSE: Execute searches together with brief text explaining what you're searching for
2. SECOND RESPONSE (after receiving results): Final analysis report with NO additional tool calls

**CRITICAL RULES**:
- ALWAYS include explanatory text with your tool calls
- Execute each search exactly ONCE in your first response
- After receiving search results, your NEXT response must be the final report with NO tool calls
- Do NOT repeat searches even if results seem incomplete
```

**Result**: Framework analysis dropped from 14-15 iterations to 2-3 iterations (80% reduction). Other providers (Claude, OpenAI) were not negatively affected.

**When to apply**: Gemini-based workflows, tool-heavy operations, or any scenario with silent tool repetition.

## Related Documentation

- [MCP Integration Guide](https://github.com/waynesun09/cicaddy/blob/main/docs/mcp-integration.md) — MCP server configuration
- [Configuration Guide](configuration.md) — GitLab CI/CD variables and AI providers
- [Token-Aware Execution](https://github.com/waynesun09/cicaddy/blob/main/docs/token-aware-execution.md) — Resource management and degradation
