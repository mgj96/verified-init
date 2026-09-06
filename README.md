# verified-init

**`/init` writes a CLAUDE.md by guessing. This writes one by proving.**

A Claude Code skill and CLI that reads your repository and emits a `CLAUDE.md`
in which **every line names the file it came from**. No model call, no network,
no subprocess, no tokens. Python standard library only.

---

## The problem

`/init` reads your repository, then a language model writes plausible-sounding
project instructions. Some are true. Some were true two quarters ago. You cannot
tell which, because **no line carries a source**.

Then the codebase moves — a script is renamed, a directory is deleted, the Java
level bumps — and `CLAUDE.md` quietly starts lying to every session that reads
it. You pay tokens for the lie, on every run, forever.

There are good linters for the second half of that problem
([agents-lint](https://github.com/giacomo/agents-lint),
[cclint](https://github.com/felixgeelhaar/cclint),
[claude-drift](https://github.com/marky291/claude-drift)). They audit a file
someone else wrote.

**Nobody closed the loop.** Generators do not verify; verifiers do not generate.

## What this does instead

Deterministic code, not a prompt. It reads your manifests and your filesystem,
and if it cannot prove something it does not write it — it tells you what it
looked for and did not find.

```console
$ verified-init --report .
verified-init  /home/me/verified-init
detectors: misc, repo

VERIFIED (4)  read from a declared source
  + py.name
      Python project `verified-init`.
      evidence: pyproject.toml -> name
  + py.version
      Requires Python >=3.9.
      evidence: pyproject.toml -> requires-python = ">=3.9"
  + repo.ci
      CI runs on GitHub Actions: `ci.yml`.
      evidence: .github/workflows/ -> 1 workflow file(s)
  + repo.ignored
      Generated or ignored directories (do not edit): `__pycache__/`, `build/`, ...
      evidence: .gitignore -> 5 directory pattern(s)

INFERRED (1)  matched a convention, not declared
  ? repo.layout.tests
      Tests live in `tests/`.
      evidence: tests/ exists (conventional test directory name)

4 verified, 1 inferred, 0 not found
```

That output is real — it is this repository describing itself.

## Install as a Claude Code skill

```sh
git clone https://github.com/mgj96/verified-init.git
```

Then link the skill into Claude Code:

```sh
# macOS / Linux
ln -s "$PWD/verified-init/skills/verified-init" ~/.claude/skills/verified-init
```

```powershell
# Windows
cmd /c mklink /D "%USERPROFILE%\.claude\skills\verified-init" "%CD%\verified-init\skills\verified-init"
```

Copying the directory works too. Ask Claude Code to *"write a CLAUDE.md for this
repo"* or *"check whether our CLAUDE.md is still accurate"* and the skill takes
over. The repo also ships `.claude-plugin/plugin.json`, so it can be installed
as a plugin from a marketplace entry.

**The skill's entire job is to run the tool and not paraphrase it.** That is the
design, not a limitation: a skill made of prompt instructions drifts when the
model changes; a skill that shells out to deterministic code does not.

## Use as a CLI

```sh
pip install verified-init      # or just run it from the clone
```

```sh
verified-init                  # write/update CLAUDE.md + .verified-init.json
verified-init --report         # print the evidence table, write nothing
verified-init --check          # exit 1 if the repo drifted from the baseline
verified-init --json           # machine-readable claims
verified-init --out AGENTS.md  # the cross-agent filename instead
```

From a clone with nothing installed: `python -m verified_init --report .`

Exit codes: `0` ok / no drift, `1` drift detected, `2` nothing provable.

## Three tiers, and why the third one matters

| Tier | Meaning |
| --- | --- |
| plain bullet | **Verified** — read from a file the project maintains |
| `_(inferred)_` | **Inferred** — a convention matched, nothing declares it |
| `## Not found` | **Checked for and absent** |

Most tools only tell you what they found. The third tier separates *"this
repository has no test directory"* from *"nobody looked."*

`src/test/java/` existing does not prove tests live there — it proves a
directory exists, so that is `_(inferred)_`. `<maven.compiler.release>17` in
your `pom.xml` is a declaration, so that is verified. The distinction is the
whole product.

## Drift detection in CI

```yaml
- run: python -m verified_init --check .
```

Commit `.verified-init.json` and every pull request that renames a script or
deletes a directory fails until `CLAUDE.md` is regenerated:

```console
$ verified-init --check .
verified-init: CLAUDE.md has drifted from the repository
  - repo.layout.src  (no longer true)
  ~ node.script.test
      was: `npm run test` -> `jest`
      now: `npm run test` -> `vitest`

Run `verified-init` to regenerate.
```

## Your prose is safe

The generated text lives between two markers. Anything outside them survives
regeneration, so hand-written context can live in the same file:

```markdown
<!-- verified-init:begin -->
...generated, do not edit...
<!-- verified-init:end -->

## Architecture notes

Written by a human. Never touched by the tool.
```

## What it reads

| Detector | Sources |
| --- | --- |
| `node` | `package.json` (packageManager, engines, scripts, workspaces, type), lockfiles, `tsconfig.json`, `.nvmrc` |
| `java` | `pom.xml` (artifactId, compiler level, modules), `build.gradle[.kts]` (toolchain, sourceCompatibility), `settings.gradle[.kts]`, `mvnw` / `gradlew` |
| `misc` | `pyproject.toml`, `requirements.txt`, `uv.lock` / `poetry.lock`, `go.mod`, `Cargo.toml`, `Makefile` (`.PHONY` only) |
| `repo` | `.github/workflows/`, `.editorconfig`, `.gitignore`, other agent instruction files, conventional source and test directories |

## What it will never do

- **Execute your code.** No build, no scripts, no `--dry-run`. Safe to run on a
  repository you have not read, and safe in CI.
- **Open a socket.** Nothing uploaded, nothing fetched.
- **Call a model.** Zero tokens, on any plan, forever.
- **Invent a claim.** `Claim()` raises if handed no evidence — the rule is
  enforced by the constructor, not by discipline.
- **Claim its own output.** The file being written is excluded from detection,
  so generating it cannot make the next `--check` report phantom drift.

## Determinism is a tested property

The same tree yields the same bytes: on any machine, on any day, driven by any
agent or model version. Directory listings are sorted, claims are ordered by
section then id, and no timestamp is recorded.

```sh
python -m unittest discover -s tests -v
```

44 tests, no dependencies. `TestDeterminism` pins the property down explicitly,
alongside a regression for the self-reference bug the suite caught during
development, and `TestSkillPackaging` guards the skill directory so the runner
cannot silently stop resolving the package.

## Prior art

This exists because of the tools it does not replace. `agents-lint`, `cclint`
and `claude-drift` audit instruction files that already exist, and do it well.
`verified-init` is the other half: it produces the file in the first place, with
the evidence attached, so there is something worth auditing.

## License

MIT
