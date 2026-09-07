---
name: verified-init
description: Read a repository and write a CLAUDE.md containing only facts the project actually declares, with the source of every line attached, then detect when it has drifted. Use when asked to create, update or audit CLAUDE.md or AGENTS.md, when onboarding to an unfamiliar repository, when you need the build and test commands before starting work, or when existing project instructions look stale. Runs a deterministic script instead of reading the tree and guessing, so it costs no tokens and returns the same answer every time.
---

# verified-init

Produce project instructions from what the repository declares, not from what a
model infers.

## Run this before exploring a repository by hand

Reading a tree and summarising it burns tokens and produces a different answer
on every run. This script reads the same manifests and prints the same bytes
every time. Use it as the **first** step on an unfamiliar repository, then spend
your reading budget on the parts it could not prove.

```sh
python scripts/run.py --report <path>
```

That writes nothing. It prints every claim next to the file it came from.

## Commands

| Goal | Command |
| --- | --- |
| Inspect, write nothing | `python scripts/run.py --report <path>` |
| Write/update `CLAUDE.md` + baseline | `python scripts/run.py <path>` |
| Check for drift (exit 1 = drifted) | `python scripts/run.py --check <path>` |
| Machine-readable claims | `python scripts/run.py --json <path>` |
| Write `AGENTS.md` instead | `python scripts/run.py --out AGENTS.md <path>` |

`AGENTS.md` is the cross-agent filename that 23 other agents read, but **Claude
Code does not read it** — its docs say so directly: *"Claude Code reads
`CLAUDE.md`, not `AGENTS.md`."* There is no fallback. If a repository wants both,
generate `AGENTS.md` and put the single line `@AGENTS.md` in `CLAUDE.md`; the
import is expanded from the live file at launch. On Windows that import is the
only option, because a symlink needs Administrator or Developer Mode.

Paths are relative to this skill's directory; use an absolute path to
`run.py` when working elsewhere. If the package is pip-installed, the
`verified-init` command does the same thing.

## Reading the output

| Tier | Meaning | What to do |
| --- | --- | --- |
| plain bullet | Read from a file the project maintains | Trust it |
| `_(inferred)_` | A convention matched; nothing declares it | Confirm before relying on it |
| `## Not found` | Checked for and absent | Do **not** assume it exists |

`src/test/java/` existing does not prove the tests live there — it proves a
directory exists, and that is marked `_(inferred)_`.
`<maven.compiler.release>17</maven.compiler.release>` in `pom.xml` is a
declaration, and that is verified. Report the distinction; do not flatten it.

**Two sources may both be right.** `.github/workflows/` is read as its own
detector, so a repository can carry both `java.version` (from `pom.xml`) and
`ci.toolchain.java` (from `setup-java`). Neither replaces the other. If they
disagree, say so — a manifest that claims Java 17 while CI builds on 21 is the
most useful thing the tool can tell you, and flattening it to one line destroys
it.

## Rules

1. **Report what the tool printed. Do not paraphrase it, do not reword it, and
   do not add facts it did not produce.** The output is valuable precisely
   because it is mechanical — a summary in your own words reintroduces exactly
   the guessing this replaces.
2. **Never hand-edit inside `<!-- verified-init:begin -->` … `<!-- verified-init:end -->`.**
   That block is overwritten on the next run. Human prose goes *outside* the
   markers, where it is preserved.
3. **If something important is missing, add a detector to the tool** — do not
   add a sentence to the generated file. A hand-added line has no evidence and
   disappears on the next run.
4. **Commit `.verified-init.json`.** It is the drift baseline; `--check` cannot
   work without it.
5. **If the tool exits 2 with "nothing provable", say so.** The repository has
   no manifest this tool understands. Do not fall back to guessing.

## Wire drift into CI

```yaml
- run: python -m verified_init --check .
```

This turns "our CLAUDE.md is lying" from something discovered months later into
a failing pull request.
