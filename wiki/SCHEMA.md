# Project Wiki Schema

## Purpose

This Git-tracked wiki stores curated, durable project knowledge. Tickets, working notes, chats, sessions, secrets, and unreviewed or short-lived content do not belong here.

`raw/` is a separate evidence store. Curated pages derive knowledge from its sources or from stable external sources.

## Root

```text
index.md   # entry point
SCHEMA.md  # these rules
log.md     # append-only change log
raw/       # evidence store
```

The root contains no curated knowledge pages.

## Navigation and Grouping

- Organize knowledge into subject domains and, when needed, subdomains.
- Create a domain or subdomain with its first knowledge page: create the directory and its corresponding index together. Do not create empty placeholder areas.
- Group related knowledge pages in a shared directory. Use the named group index only for navigation; do not add an overview page solely to summarize the group. Create child pages only when their content must be referenced, updated, or retrieved independently.
- `index.md` is the only root index. Give every directory outside `raw/` its own named index.
- Keep indexes free of frontmatter. Briefly describe their immediate contents and link to active pages in the same directory and indexes of direct subdomains.
- Exclude inactive pages from every index.
- Use pathless wikilinks with the unique filename: `[[filename]]`. Aliases and section anchors are allowed. Do not create artificial placeholder pages.

## Names

Keep filenames unique across the wiki.

- Directory names: lowercase; join words within a term with `-`.
- Use `_` only to separate domain levels; use `-` to join words within a level or term.
- Domain indexes: use the full directory path in uppercase, separate levels with `_`, and append `_INDEX.md`.
- Knowledge pages: use the full domain path in lowercase, separate levels with `_`, and append `_` plus a descriptive lowercase title.

```text
research/source-quality/RESEARCH_SOURCE-QUALITY_INDEX.md
research/source-quality/research_source-quality_evaluation.md
```

## Curated Knowledge Pages

Every page must meet at least one of these criteria: document a decision; describe a system, concept, procedure, or project with long-term relevance; distill reusable insights from multiple sources; or serve as a central reference in its own right.

```yaml
---
title: ...
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: active | inactive
tags: [...]
sources: [...]
# optional:
# confidence: high | medium | low
# review_by: YYYY-MM-DD
# contested: true
---
```

- Include at least one permitted tag in `tags`.
- Include at least one source in `sources`: a wikilink to a curated page, a wiki-relative `raw/` path, or a complete external URL.
- Update the existing page about the same topic in the same domain when new evidence arrives. Git preserves its previous version.
- Use `active` for navigable, valid knowledge.
- Use `inactive` for knowledge that is no longer valid. Do not index it, link to or from active curated pages, or retain wikilinks to curated pages in its body or `sources:`. Preserve raw paths and external URLs.

## Raw Evidence

`raw/` is not a wiki domain: it has no indexes and no naming convention. Do not modify an evidence object after ingestion; add corrections or new versions as new evidence objects.

- Give Markdown sources frontmatter with `title`, `owner`, and `created_at`. `source_url` is optional and applies only to web pages.
- Give non-Markdown sources a `.meta.yaml` sidecar file with the same base name and metadata.
- Leave existing evidence objects unchanged when metadata rules are introduced later.
- Mirror external sources only when they are critical, internal, or not reliably available over time.

## Tags

Use only tags documented here. Add new tags to this section before applying them. This generic starting set may be adapted to the project:

```text
concept, decision, governance, operations, process,
project, reference, research, system
```

## Changes

- Follow the repository Gitflow and commit every completed curation change locally.
- List every new or modified curated page in the relevant index unless it is inactive, and document it in `log.md`.
- Keep `log.md` append-only and follow its recorded format.
