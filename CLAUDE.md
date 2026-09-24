# Claude Code entry point

Read [AGENTS.md](AGENTS.md) and follow [docs/agent-start.md](docs/agent-start.md).

Baseline setup: `python scripts/setup.py`. It generates `workspace-data/mcp.json` with absolute paths. Connect with `claude --mcp-config workspace-data/mcp.json`, then approve the local server in Claude Code. Authentication and MCP trust remain user-controlled. Shell access also works directly through `python scripts/workspace.py`; MCP is optional.

Using Claude to research the archive and selecting Claude Code as the app's tracked review provider are separate workflows. Consult the agent-start guide for their requirements and verification status.
