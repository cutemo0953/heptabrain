---
description: "Restructure a wiki-format KB — merge duplicates, update stale entries, relocate misplaced items. Usage: /kb-restructure blog-research or /kb-restructure all"
argument-hint: "blog-research | wearable-sensor | safety-ii | all"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# KB Restructure — Living Wiki Maintenance

Extracted from `/research-digest` Step 5 as an independent atomic skill.

**Input:** A KB name (or "all")
**Output:** Restructured KB file(s) with duplicates merged, stale entries updated, misplaced entries relocated.

## Arguments

`$ARGUMENTS` = one of:
- `blog-research` → `~/your-blog-repo/docs/KNOWLEDGE_BASE_BLOG_RESEARCH.md`
- `wearable-sensor` → `~/Downloads/wearable-sensor-kb/KNOWLEDGE_BASE.md`
- `safety-ii` → `~/Downloads/safety-ii-kb/KNOWLEDGE_BASE.md`
- `all` → all of the above

## Instructions

For each target KB:

### 1. Read the full KB file

### 2. Merge duplicates
- If the same study/topic appears in multiple places (from different digest runs), consolidate into one entry with the most recent data
- Keep the most complete version, add `[Merged {date}]` tag

### 3. Update stale data
- If a newer finding supersedes an existing entry (e.g., CMS TEAM hospital count changed), update the existing entry in-place with `[Updated {date}]` tag
- Don't create a second entry — update the original

### 4. Relocate misplaced entries
- If a recent append belongs in an existing section, move it there
- Don't leave entries floating at the bottom of the file

### 5. Propose new sections
- If 3+ entries share a theme that doesn't match any existing section, create a new section header and move them in

### 6. Trim low-value entries
- Entries tagged KB-KNOWN for 3+ consecutive digests with no new development: mark `[Stable — no recent updates]`
- Do NOT delete — just tag

### 7. Cross-KB connections (if `all`)
- After restructuring each KB individually, scan across all KBs for:
  - Same topic appearing in multiple KBs → note the cross-reference
  - Contradicting data between KBs → flag
- Add a "Cross-KB References" section at the bottom of each KB if findings exist

### 8. Rewrite the KB file
- Preserve all source URLs and DOIs
- Maintain the existing section structure (don't reorganize entire TOC unless needed)
- Output a summary of changes:

```
## KB Restructure Report — {date}

KB: {name}
- Merged: {N} duplicate entries
- Updated: {N} stale entries
- Relocated: {N} misplaced entries
- New sections: {N}
- Trimmed: {N} low-value entries
- Cross-KB refs: {N} (if applicable)
```

## Important Rules

- This is about STRUCTURE, not CONTENT. Don't add new research findings — that's `/research-digest`'s job.
- Don't delete anything. Merge, relocate, tag — never delete.
- Preserve all URLs and DOIs exactly as-is.
- The KB should read like a well-organized reference, not a chronological dump.
- All output in zh-TW.
