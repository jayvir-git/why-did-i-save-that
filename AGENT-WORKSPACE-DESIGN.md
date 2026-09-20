# Agent research workspace: clarified design

Status: v1 provides capture, extraction, full extracted-text passage search, hybrid retrieval, reusable versioned research, media review queues, CLI/MCP and a local web app. See README.md for shipped behavior. Automatic video transcription, authenticated browser expansion and remote refresh remain future adapters.

## Purpose and boundaries

Give agents a persistent, programmable environment in which to investigate the user's saved material. Agents can inspect the entire available corpus, write analysis code, invent and test classifications, enrich evidence, compare interpretations, and preserve reusable results. The system does not force a fixed workflow, model provider, taxonomy, research question, or explorer/critic pairing.

The browser extension is an ingestion client. The human library is an optional inspection and steering interface. Neither is the primary agent interface.

The system can establish what was captured and what an investigation did. It cannot reconstruct a person's original reason for saving a post or guarantee that X exposed every historical save. Inferred interests and inferred motives must remain distinguishable from explicit user statements.

Agents do not need human-sized review batches, a readable feed, or manual confirmation of every internal finding. They still operate with finite context, compute, permissions, source availability, and imperfect reasoning. The design removes unnecessary interaction constraints while making those remaining constraints observable.

## Decisions that replace ambiguities in the original plan

### 1. The product is an environment for agents, not one built-in agent

A shared local engine owns data access and mutations. A CLI, a small SDK, and an MCP adapter expose the same engine operations. Existing agents bring their own models, reasoning loops and delegation. No cloud model account is required to read or analyze the dataset locally; an external agent may nevertheless use a remote model, so local storage alone does not imply local inference.

A bundled embedding model is a replaceable retrieval aid. Agents can use exact queries, semantic queries, their own embeddings, corpus exports or custom code. They can inspect how any ranking was produced.

### 2. Use ordinary, accessible storage

Use SQLite for canonical metadata, relationships, observations, full-text search and job state. Store raw captures and larger artifacts as content-addressed files. Store vector indexes as rebuildable derived artifacts, identified by model revision and input fingerprint. At the present collection size, exact vector comparison is sufficient; a separate vector service is unnecessary initially.

Provide a documented read-only SQL connection and snapshot exports in JSONL/Parquet where appropriate. Agents can run Python or other analysis in their own workspace using those inputs. Canonical writes go through transactional engine operations, not arbitrary SQL. This protects provenance and concurrency without limiting the analyses agents can perform on exported data.

First ingestion imports the existing JSON backup. A later incremental bridge lets the extension send new observations to the local engine. Do not access Chrome's internal profile database or assume a localhost bridge already has browser permission. Existing capture, deduplication and export code can be reused; the UI need not be rebuilt first.

### 3. Distinguish objects, observations and interpretations

Core records:

- Object: post, linked page, repository, media item or thread; stable internal ID plus source identity.
- Observation: an immutable captured version, raw artifact hash, collection time, author/source metadata, extraction method and known omissions.
- Save membership: account, post, observed source (like/bookmark), observed time and collection run. Absence from an incomplete crawl is not evidence of removal.
- Relationship: replies to, quotes, links to, part of thread, duplicate candidate, or agent-proposed relationship; distinguish source-observed edges from inferred edges.
- Derived artifact: chunk, embedding, extraction, topic assignment, collection or analysis, with input versions, producing tool/model, parameters and timestamp.
- Claim: a statement linked to specific evidence, counterevidence, assumptions and status.
- Investigation: objective, working artifacts, jobs, result sets, claims, concise decision summaries and unresolved questions.

Retain captures before interpretation. Corrections create superseding versions rather than silently rewriting prior evidence. Keep original and normalized text separately so citations can resolve to the captured source.

### 4. Discovery primitives should compose

The logical interface has a small set of operations, each supporting batches:

- Inspect schema, available fields, corpus inventory, source coverage, model versions and job capabilities.
- Query structured filters, exact/full-text search, semantic search, or read-only SQL.
- Materialize a result set at a named dataset revision; retrieve projected fields, chunks or full records by ID/cursor.
- Expand relationships or retrieve selected external resources.
- Write/version artifacts, claims, collections, tags and proposed relationships.
- Start, inspect, cancel and resume asynchronous jobs and investigations.

Do not return thousands of repeated JSON tool messages. A query returns a result-set handle, counts, scope, ranking details, and a small configurable preview. The agent can then request all IDs, stream records, batch-fetch full content, export the entire set or run code over it. Preview size is a transport choice, not a research limit. Every omitted field and clipped value is explicit.

SQL and bulk export provide an escape hatch when a predefined operation does not express the agent's question. Agents can create new analyses without requiring us to add another tool endpoint.

### 5. Define coverage precisely

Separate four different statements:

1. The backup contains N records.
2. The relevant representation exists for N of those records, such as searchable text or image OCR.
3. This investigation processed N records from a declared snapshot.
4. Retrieval found N candidates under specified criteria.

None of these establishes perfect semantic recall or a complete X history.

A query receipt records dataset revision, universe and filters, exact or estimated match count, records returned, missing representations, errors, whether further pages exist, and ranking/model versions. Approximate searches say so. An exhaustive SQL count can support an exhaustive claim within its defined snapshot; a top-k semantic search cannot.

An agent may scan every record and run several retrieval strategies. It must not describe that as having analyzed unextracted images, missing thread replies or unavailable linked pages.

### 6. Enrichment is an explicit dependency graph

Retrieving a page, expanding a thread, OCR, transcription and repository inspection are separate jobs with immutable input/output versions. Support both selective enrichment and bulk enrichment of the entire authorized corpus. Avoid mandating one-post-at-a-time or on-demand-only processing.

Jobs expose pending, running, completed, partial, failed and cancelled states; progress, coverage, attempts, retryability and failure reason. Reuse unchanged resources; refresh when the investigation needs current information. Keep failed and unavailable resources in the inventory.

Use the agent's granted account/browser capabilities for authenticated sources. Public-resource fetching does not imply access to unrelated accounts or internal network services. Retrieved content is untrusted data and cannot grant tools new authority.

### 7. Value must be evaluated against a named objective

Remove the global assumption that bookmarks, code links or career posts are inherently the most valuable saves. Those heuristics can be named baselines, not a universal gold score.

An investigation supplies or proposes an objective and criteria. For example: identify a small portfolio project; rediscover enjoyable comedy; compare conflicting explanations; find neglected recurring interests. If the user gives no objective, the agent may produce several explicit hypotheses and explore them without blocking on a question.

Persist explicit preferences separately from inferred interests. A click, a like or acceptance of a content label does not automatically prove a personal goal. Preference inferences can be revised, rejected or superseded.

### 8. Evidence links must resolve to the supporting material

A claim records its scope, evidence observation IDs and exact spans, counterevidence, method and status: proposed, supported, disputed or superseded. Media evidence uses available coordinates or timestamps. A source URL alone is not sufficient because a page can change or fail to support the claim.

Keep separate claims for separate propositions. A saved hiring post supports “this company advertised a role at this time,” not “this role is open today.” The latter needs current evidence.

Attach uncertainty to its cause: inaccessible source, ambiguous wording, weak retrieval match, conflicting sources, or inferred motivation. Do not present uncalibrated model similarity as a probability of truth. A second agent agreeing is not independent evidence.

The investigation log stores operations, resulting evidence and concise decisions, not hidden model chain-of-thought.

### 9. Autonomy inside the workspace is the default

Agents may freely query, scan, create code and derived artifacts, invent labels, build collections, test hypotheses, reject their own ideas, and revise their own outputs within the authorized local workspace. These activities do not require repeated human approvals.

Preserve user-authored decisions, provenance and original evidence. A later agent can propose alternatives or supersede its own annotations without silently overwriting the user's statements. Reversible derived changes have an activity log and rollback. Source-account mutations and irreversible destruction remain separate operations requiring applicable authorization.

The distinction between user and agent annotations identifies authorship; it is not a mandatory human review gate for every agent output.

### 10. Persistent jobs and concurrent work are first-class

Research jobs use stable IDs, idempotency keys, checkpoint cursors and cancellation. They run against explicit dataset snapshots. Artifact writes use transactions and expected revisions to detect conflicting changes. Multiple agents can work on isolated investigation branches and merge chosen outputs with their provenance intact.

Each investigation can report wall time, tool calls, coverage and model usage where available. Limits are configurable, not arbitrary UI limits. Agents should stop or re-plan when further work yields no new evidence, a dependency is unavailable, or a declared resource bound is reached. The result can be partial with a resumable next step.

Multiple agents are optional. Useful independent tasks include checking different source partitions, proposing alternative clusters, or searching for counterexamples to a concrete claim. Do not require an explorer/critic debate for every operation.

## A concrete example

Objective: find three plausible portfolio projects grounded in saved resources.

1. Inspect the inventory and choose a snapshot. Record which posts lack useful text and which links have not been retrieved.
2. Use exact search, semantic search and a bulk scan to construct candidate sets. Save query receipts and candidate IDs.
3. Investigate several competing project themes, inspecting actual posts and related resources. Derive themes rather than restricting them to the seven current labels.
4. Retrieve promising repositories and documentation within the granted access. Record current availability, prerequisites and relevant terms where they affect feasibility.
5. Evaluate candidates against explicit criteria. Unknown user time or skills become stated assumptions or alternative scenarios, not invented facts.
6. Seek counterevidence: redundant ideas, missing prerequisites, unavailable resources or a scope that does not fit the assumed goal.
7. Save three project dossiers containing a rationale, evidence spans, useful source collections, a first experiment, assumptions and unresolved questions. Preserve rejected alternatives and the reason for rejection.
8. A later agent can continue any dossier using its snapshot, artifacts and recorded gaps.

## Implementation order and completion criteria

1. Foundation: import backup idempotently; expose schema, versioned observations, query receipts, read-only SQL and complete exports. Verify all imported records and source memberships survive a round trip without invented content or lost provenance.
2. Agent access: implement the shared engine plus CLI/SDK/MCP adapter, snapshot result sets, batch retrieval and persisted investigations. An agent must be able to inspect and analyze the entire available corpus without the visual library.
3. Evidence and enrichment: add versioned artifacts, evidence spans, explicit claims, resumable enrichment, failures and invalidation of stale derivatives. Interrupt a job and verify resume produces the same logical result without duplicate records.
4. Exploration: support emergent taxonomies, collections, arbitrary analysis artifacts, alternative hypotheses and reversible merges. Demonstrate that agents can create a new analysis without a UI change or a new endpoint.
5. Evaluation: use controlled fixtures for exhaustive queries, known paraphrases for retrieval, stale and unavailable resources, contradictory evidence and malicious source instructions. Check factual support, provenance, coverage honesty and whether another agent can reproduce the important result sets. Then exercise real investigations on the user's corpus. No requirement to manually label every saved post.

The first release is complete when an agent can independently inventory, query, bulk-analyze, save an evidence-backed investigation, stop, and resume it through the local interface. Do not defer that core loop while polishing dashboards or choosing a multi-agent framework.
