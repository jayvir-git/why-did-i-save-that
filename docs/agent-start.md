# Start with your agent

Give a local coding agent this prompt after cloning the repository:

> Read AGENTS.md and docs/agent-start.md. Set up the baseline app using scripts/setup.py, run its disposable demo, and report which capabilities work and which need my input. Use the generated CLI or MCP interface for research. Do not import personal data, download optional models, or start a paid provider review unless I request it. Help me connect my collection after setup passes.

The baseline requires Python 3.12+ with SQLite FTS5. No AI account, model, Node.js or browser is needed for setup verification. A harness needs local filesystem and command access, or the ability to launch a local stdio MCP server. A remote chat with no access to this machine cannot reach its local archive.

## One setup command

```sh
python scripts/setup.py
```

This checks Python and the database, runs import → keyword search → cited note → safe replay → MCP handshake in a temporary synthetic archive, initializes the real workspace without importing data, and writes `workspace-data/mcp.json`. It returns a JSON status, provider executable availability and next steps. It never spends provider usage. Run it again after correcting a reported error; saved evidence is preserved.

Optional downloads and packages must be selected explicitly:

```sh
python scripts/setup.py --with extension --with semantic --with extraction
```

`extension` downloads the collector's inference assets. `semantic` installs the local meaning-search runtime and downloads model assets. `extraction` installs HTML/PDF/OCR dependencies. Successful installs are recorded so repeated setup can reuse them. Model downloads and package installation need network access; package availability depends on the Python/platform combination. Setup failure reports the failed command and remains retryable.

Selected semantic setup verifies a real embedding on synthetic text. Extraction setup verifies dependency imports; remote capture and OCR model initialization remain separate checks. Use `--reinstall` with the selected `--with` options to repair an existing dependency installation.

After importing a collection, run `python scripts/workspace.py index_attachments` for meaning search. Extraction is explicit through the app or `scripts/enrich_library.py --run`; setup does not fetch links from your private collection.

Use `--workspace /absolute/path` for a separate archive. Configuration contains machine-specific paths and belongs outside version control. `--mcp-output /path/to/config.json` merges a `gold-workspace` entry while preserving other servers; it refuses to overwrite a conflicting entry. It does not edit global agent settings.

## Connect an agent

**Claude Code:** start from the repository with:

```sh
claude --mcp-config workspace-data/mcp.json
```

Approve the local server when prompted. Ask Claude to call `inventory` and inspect `catalog` through the CLI, or discover the MCP tools. See [Claude Code's MCP documentation](https://code.claude.com/docs/en/mcp).

**Other MCP clients:** copy the generated `mcpServers.gold-workspace` entry into the client's supported configuration. Client-specific trust, settings and transport support vary. The server supports local stdio, not a remote HTTP MCP endpoint.

**Any harness with shell access:** run `python scripts/workspace.py catalog`, then `python scripts/workspace.py inventory`. Pass operation arguments through an UTF-8 JSON file with `--args-file`. `--workspace` goes before the operation. The absolute launcher resolves the project and default archive even when launched from another directory.

For research, read [WORKSPACE.md](../WORKSPACE.md): retrieve full result pages, cite exact immutable source spans, preserve uncertainty, and use stable request IDs for retryable saves. Tools return explicit coverage and version information. A source quote matching a stored span does not prove an interpretation correct.

## Tracked reviews in the app

Choose **Codex** or **Claude Code** in the review's **Review provider** selector. The app records the chosen provider with the run; cancellation, timeout, progress, quota errors and draft acceptance work through the same UI. One active run per review prevents duplicate work across providers. To switch providers, cancel the active attempt first.

- Codex requires an installed, signed-in CLI; `GOLD_CODEX_BIN` can specify its executable.
- Claude Code requires an installed, signed-in CLI supporting `-p`, stream JSON, `--json-schema`, `--safe-mode` and `--no-session-persistence`; `GOLD_CLAUDE_BIN` can specify its executable. Use the native executable on Windows, rather than a shell alias or `.cmd` wrapper.
- Sign in yourself using `codex login` or `claude auth login`. Setup only checks executable availability; it does not certify authentication or available usage.
- Reviews supply selected captured text (up to 60,000 characters) and an optional supported image to the selected provider. Claude images are limited to 5 MB. Claude runs with built-in tools disabled, empty MCP configuration and customization disabled. Codex uses its existing read-only ephemeral runner. Neither runner automatically accepts its output as evidence.

Protocol references: [Claude CLI](https://code.claude.com/docs/en/cli-reference), [programmatic output](https://code.claude.com/docs/en/headless). Unsupported flags, missing credentials and provider failures must be resolved visibly; the app does not silently switch providers.

## Verification and human steps

Run `python scripts/demo.py` for the disposable workflow alone. Run `python scripts/check_fresh_install.py` to copy public source into a clean temporary directory, omit runtime/models/private data, run setup twice from another working directory, and verify the generated launcher. CI runs this baseline on Windows and Linux.

The Claude adapter is covered by synthetic protocol tests. A live authenticated Claude review has not been verified on the development machine because Claude Code is not installed. The synthetic checks do not establish compatibility with every CLI release or harness. The Codex runner has previously passed a synthetic live review.

The user still loads the Chrome extension, signs into X, chooses collection scope, pairs the bridge and signs into any review provider. These are explicit handoffs, not hidden setup failures. A successful baseline is a working empty workspace and a verified disposable workflow—not a claim that personal data or optional providers are ready.
