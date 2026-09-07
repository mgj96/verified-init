# verified-init

Generates a `CLAUDE.md` in which **every line names the file it came from**, and
fails CI when the repository no longer matches it. No model call, no network, no
subprocess, no tokens — Python standard library only.

Built because I needed deterministic, offline generation for air-gapped work,
where a model-driven `/init` is not an option and a tool that phones home is not
allowed. It is a personal tool published in case it is useful to someone with
the same constraint.

## This is a crowded space — read this before installing

Several projects already cover adjacent, overlapping ground, and most of them
are further along:

| Project | What it does |
| --- | --- |
| [ctxlint](https://www.npmjs.com/package/@yawlabs/ctxlint) | The most established linter here. Rules include `paths/not-found`, `paths/glob-no-match`, `commands/script-not-found`, `commands/make-target-not-found`, `staleness/stale` |
| [agnix](https://github.com/agent-sh/agnix) | 455 rules, GitHub Action, SARIF output, IDE extensions |
| [agentsgen](https://github.com/markoblogo/AGENTS.md_generator) | Python, deterministic, marker-based safe updates, `--check` and a drift-gating Action |
| [agents-lint](https://github.com/giacomo/agents-lint) | Generates with `agents-lint init`, then lints the result |
| [rulesync](https://github.com/dyoshikawa/rulesync) | Deterministic generation across 40 agent formats, with `generate --check` |
| [plinth](https://github.com/jabrena/plinth) | Generates AGENTS.md for Java projects, distributed via Maven Central |
| [claude-drift](https://github.com/marky291/claude-drift) · [cclint](https://github.com/felixgeelhaar/cclint) | Audit CLAUDE.md, skills and agents against the codebase |

If you want a maintained linter, use ctxlint or agnix. If you want generation on
the JVM, use plinth. **Reach for this one only if you specifically need
generation that runs with no network, no model, and no dependencies** — which is
the narrow reason it exists.

One more thing worth knowing before you adopt any of these: Anthropic's own
guidance tells you to keep *pitfalls, rationale and conventions* out of the
derivable pile, and Claude Code's `/doctor` offers to **delete** directory
layouts, dependency lists and architecture overviews from a checked-in
`CLAUDE.md`. A measurement across 138 repositories and 5,694 PRs
([arXiv:2602.11988](https://arxiv.org/abs/2602.11988)) found context files did
not improve task success while raising inference cost by over 20%. Generated
repo overviews are not free, and they may not be worth their context budget.

## What it does

Deterministic code, not a prompt. It reads your manifests and your filesystem,
and if it cannot prove something it does not write it — it tells you what it
looked for and did not find.

```console
$ verified-init --report .
detectors: java, repo

VERIFIED (10)  read from a declared source
  + java.maven.artifact
      Maven project `parking-api`.
      evidence: pom.xml -> <artifactId>
  + java.maven.stack
      Built on Lombok, Spring Boot Web (MVC), Spring Data JPA.
      evidence: pom.xml -> declared dependencies
  + java.version
      Targets Java 17.
      evidence: pom.xml -> Java level property = 17
  + java.maven.wrapper
      Use the bundled Maven wrapper (`./mvnw`); no system Maven required.
      evidence: mvnw present
  + java.maven.build
      Build with `./mvnw package`.
      evidence: pom.xml present (standard Maven lifecycle)
  + java.maven.testframework
      Test stack: Spring Boot Test, Testcontainers.
      evidence: pom.xml -> declared dependencies
  + repo.ci
      CI runs on GitHub Actions: `build.yml`.
      evidence: .github/workflows/ -> 1 workflow file(s)
  ...

INFERRED (3)  matched a convention, not declared
  ? java.layout.src.test.java
      Tests live in `src/test/java/`.
      evidence: src/test/java/ exists (standard Maven/Gradle layout, not declared in the build file)
  ...

10 verified, 3 inferred, 0 not found
```

Real output from a Spring Boot project, abbreviated at the `...` marks.

Note what is *not* claimed. `Built on Spring Boot Web (MVC)` is verified because
`spring-boot-starter-web` is declared in `pom.xml`. `Tests live in src/test/java/`
is only inferred, because the directory exists but no build file says that is
where tests come from. The tool will not upgrade the second one to the first.

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
| `node` | `package.json` — description, license, packageManager, engines, scripts, workspaces, `type`, **declared dependencies → stack and test runner** (Next.js, React, Vue, VitePress, Astro, Nuxt, Express, NestJS, Electron, Vitest, Jest, Playwright, …); lockfiles, `tsconfig.json`, `.nvmrc` |
| `java` | `pom.xml` — artifactId, compiler level, modules, **declared `<artifactId>`s → stack** (Spring Boot Web/WebFlux/Data JPA/Security, Hibernate, Lombok, MapStruct, Quarkus, Micronaut, JUnit 5, Mockito, Testcontainers, …); `build.gradle[.kts]` toolchain and coordinates, `settings.gradle[.kts]`, `mvnw` / `gradlew` |
| `misc` | `pyproject.toml` (description, requires-python, **dependencies → Django / FastAPI / Flask / SQLAlchemy / pytest …**), `requirements.txt`, `uv.lock` / `poetry.lock`, `go.mod` (**require → Gin / Echo / GORM / Cobra**), `Cargo.toml` (**[dependencies] → Axum / Actix / Tokio / Serde**), `Makefile` (`.PHONY` only) |
| `ci` | `.github/workflows/*.yml` — **`setup-node` / `setup-java` / `setup-python` / `setup-go` versions, the `run:` steps CI actually executes, the package manager it invokes, GitHub Pages deploy target and published path** |
| `repo` | `.editorconfig`, `.gitignore`, `LICENSE`, `HANDOVER.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `SECURITY.md`, other agent instruction files, conventional source and test directories |

CI gets its own detector because it is the version of the build that has to
work. It also answers questions the manifest leaves open: a repo with no
`engines.node` and no lockfile still pins Node in `setup-node` and still names
its package manager in a `run:` step. Without reading workflows, both get
reported as absent when they are merely declared elsewhere — and both claims
stand when the manifest and CI disagree, because that disagreement is worth
seeing.

Stack detection reads the dependency the project **declared**, so it stays
verified. An unrecognised dependency produces no claim at all — a wrong stack
label would be worse than a missing one.

## What it will never do

- **Execute your code.** No build, no scripts, no `--dry-run`. Safe to run on a
  repository you have not read, and safe in CI.
- **Open a socket.** Nothing uploaded, nothing fetched.
- **Call a model.** Zero tokens, on any plan, forever.
- **Invent a claim.** `Claim()` raises if handed no evidence — the rule is
  enforced by the constructor, not by discipline.
- **Claim its own output.** The file being written is excluded from detection,
  so generating it cannot make the next `--check` report phantom drift.
- **Contradict itself.** A specific claim silences the generic one it answers:
  once `src/test/java/` is reported, the generic "no test directory found" line
  is suppressed rather than printed three lines below it.

## Determinism is a tested property

The same tree yields the same bytes: on any machine, on any day, driven by any
agent or model version. Directory listings are sorted, claims are ordered by
section then id, and no timestamp is recorded.

```sh
python -m unittest discover -s tests -v
```

66 tests, no dependencies. `TestDeterminism` pins the property down explicitly,
alongside a regression for the self-reference bug the suite caught during
development, and `TestSkillPackaging` guards the skill directory so the runner
cannot silently stop resolving the package.

## Honest limits

- **The staleness it guards against is real but not frequent.** I measured 22
  public repositories with hand-written agent context files: roughly one
  demonstrably-broken claim per repo, and about half had none at all. Re-running
  the measurement on the same files disagreed with itself often enough that I
  would not defend a precise figure. Breakage tracked whether maintainers looked
  after the file, not how much the code changed.
- **The provenance tiers are for humans, not the model.** As visible text they
  spend context budget; as HTML comments they are stripped before injection.
  They help a reviewer decide whether to trust a line. They do not change agent
  behaviour.
- **Most of what it can prove is derivable anyway.** An `@package.json` import in
  your `CLAUDE.md` is always fresh, costs no tool, and never rots. Prefer it
  wherever it fits; this tool earns its place mainly when you also want the
  CI drift gate and the tiering.
- **Not a linter.** It does not check prose you wrote. ctxlint and agnix do.

## License

MIT
