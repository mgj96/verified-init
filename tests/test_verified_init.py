"""Test suite. Standard library only: run with `python -m unittest discover tests`."""

from __future__ import annotations

import json
import os
import shutil
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verified_init import (  # noqa: E402
    BEGIN,
    END,
    INFERRED,
    VERIFIED,
    analyze,
    build_state,
    diff_state,
    has_drift,
    render_agents_md,
    render_report,
)
from verified_init import frameworks  # noqa: E402
from verified_init.claims import Claim  # noqa: E402
from verified_init.cli import main  # noqa: E402


class RepoCase(unittest.TestCase):
    """Base class that builds throwaway repositories from a file map."""

    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for path in self._dirs:
            shutil.rmtree(path, ignore_errors=True)

    def fixture(self, files):
        root = tempfile.mkdtemp(prefix="verified-init-")
        self._dirs.append(root)
        for rel, contents in files.items():
            full = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(contents)
        return root


class TestClaimModel(RepoCase):
    def test_evidence_is_structurally_required(self):
        with self.assertRaises(ValueError):
            Claim(id="x", section="Setup", text="something", status=VERIFIED, evidence="")

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            Claim(id="x", section="Setup", text="t", status="probably", evidence="e")

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(ValueError):
            Claim(id="x", section="Vibes", text="t", status=VERIFIED, evidence="e")


class TestNode(RepoCase):
    def test_reads_scripts_package_manager_and_module_type(self):
        root = self.fixture(
            {
                "package.json": json.dumps(
                    {
                        "name": "demo",
                        "type": "module",
                        "packageManager": "pnpm@9.0.0",
                        "engines": {"node": ">=18"},
                        "scripts": {"build": "tsc", "test": "vitest run"},
                    }
                )
            }
        )
        a = analyze(root)
        self.assertEqual(a.by_id("node.name").status, VERIFIED)
        self.assertIn("pnpm install", a.by_id("node.pm").text)
        self.assertIn(">=18", a.by_id("node.engine").text)
        self.assertIn("vitest run", a.by_id("node.script.test").text)
        self.assertIsNotNone(a.by_id("node.esm"))

    def test_falls_back_to_lockfile_for_package_manager(self):
        root = self.fixture({"package.json": '{"name":"demo"}', "yarn.lock": ""})
        a = analyze(root)
        self.assertIn("yarn install", a.by_id("node.pm").text)
        self.assertEqual(a.by_id("node.pm").evidence, "yarn.lock present")

    def test_missing_script_becomes_a_probe_not_a_claim(self):
        root = self.fixture({"package.json": '{"name":"demo","scripts":{}}'})
        a = analyze(root)
        self.assertIsNone(a.by_id("node.script.test"))
        self.assertIn("node.script.test", [p.id for p in a.probes])

    def test_malformed_package_json_is_ignored_not_guessed(self):
        root = self.fixture({"package.json": "{ this is not json", "go.mod": "module m\ngo 1.22\n"})
        a = analyze(root)
        self.assertIsNone(a.by_id("node.name"))
        self.assertIsNotNone(a.by_id("go.module"))


class TestJava(RepoCase):
    def test_maven_reads_artifact_level_modules_and_wrapper(self):
        root = self.fixture(
            {
                "pom.xml": (
                    "<project>\n"
                    "  <artifactId>parking-api</artifactId>\n"
                    "  <properties><maven.compiler.release>17</maven.compiler.release></properties>\n"
                    "  <modules><module>core</module><module>web</module></modules>\n"
                    "</project>\n"
                ),
                "mvnw": "#!/bin/sh\n",
            }
        )
        a = analyze(root)
        self.assertIn("parking-api", a.by_id("java.maven.artifact").text)
        self.assertIn("Java 17", a.by_id("java.version").text)
        self.assertIn("`core`", a.by_id("java.maven.modules").text)
        self.assertIn("./mvnw package", a.by_id("java.maven.build").text)

    def test_maven_without_wrapper_uses_bare_mvn(self):
        root = self.fixture({"pom.xml": "<project><artifactId>x</artifactId></project>"})
        a = analyze(root)
        self.assertIn("`mvn package`", a.by_id("java.maven.build").text)

    def test_maven_without_java_level_records_a_probe(self):
        root = self.fixture({"pom.xml": "<project><artifactId>x</artifactId></project>"})
        a = analyze(root)
        self.assertIsNone(a.by_id("java.version"))
        self.assertIn("java.version", [p.id for p in a.probes])

    def test_gradle_reads_toolchain_and_subprojects(self):
        root = self.fixture(
            {
                "build.gradle.kts": "java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }\n",
                "settings.gradle.kts": 'include(":core")\ninclude(":web")\n',
                "gradlew": "#!/bin/sh\n",
            }
        )
        a = analyze(root)
        self.assertIn("Java 21", a.by_id("java.version").text)
        self.assertIn("`core`", a.by_id("java.gradle.modules").text)
        self.assertIn("./gradlew build", a.by_id("java.gradle.build").text)

    def test_gradle_groovy_source_compatibility(self):
        root = self.fixture({"build.gradle": "sourceCompatibility = '17'\n"})
        a = analyze(root)
        self.assertIn("Java 17", a.by_id("java.version").text)

    def test_standard_layout_is_inferred_never_verified(self):
        root = self.fixture(
            {
                "pom.xml": "<project><artifactId>x</artifactId></project>",
                "src/main/java/App.java": "class App {}\n",
            }
        )
        a = analyze(root)
        self.assertEqual(a.by_id("java.layout.src.main.java").status, INFERRED)


class TestMisc(RepoCase):
    def test_go_module_and_version(self):
        root = self.fixture({"go.mod": "module github.com/me/thing\n\ngo 1.22\n"})
        a = analyze(root)
        self.assertIn("github.com/me/thing", a.by_id("go.module").text)
        self.assertIn("Go 1.22", a.by_id("go.version").text)

    def test_rust_name_and_edition(self):
        root = self.fixture({"Cargo.toml": '[package]\nname = "thing"\nedition = "2021"\n'})
        a = analyze(root)
        self.assertIn("thing", a.by_id("rust.name").text)
        self.assertIn("2021", a.by_id("rust.edition").text)

    def test_python_requires_and_lockfile(self):
        root = self.fixture(
            {
                "pyproject.toml": '[project]\nname = "thing"\nrequires-python = ">=3.9"\n',
                "uv.lock": "",
            }
        )
        a = analyze(root)
        self.assertIn(">=3.9", a.by_id("py.version").text)
        self.assertIn("uv", a.by_id("py.pm").text)

    def test_make_lists_only_phony_targets(self):
        root = self.fixture({"Makefile": ".PHONY: build test\nbuild:\n\techo hi\nartifact.o:\n\ttouch $@\n"})
        a = analyze(root)
        text = a.by_id("make.targets").text
        self.assertIn("make build", text)
        self.assertIn("make test", text)
        self.assertNotIn("artifact.o", text)


class TestRepo(RepoCase):
    def test_reports_ci_and_pre_existing_agent_files(self):
        root = self.fixture(
            {
                "package.json": '{"name":"x"}',
                ".github/workflows/ci.yml": "name: ci\n",
                "AGENTS.md": "# notes\n",
            }
        )
        a = analyze(root)
        self.assertIn("ci.yml", a.by_id("repo.ci").text)
        self.assertIn("AGENTS.md", a.by_id("repo.agentfiles").text)

    def test_the_file_being_written_is_never_claimed_as_evidence(self):
        """Whatever --out names must be excluded, not just the default.

        Regression: the output file used to be listed among "other agent
        instruction files", so generating it created a claim and the next
        --check reported drift against an untouched repository.
        """
        for output in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
            with self.subTest(output=output):
                root = self.fixture({"package.json": '{"name":"x"}', output: "# existing\n"})
                a = analyze(root, output_name=output)
                claim = a.by_id("repo.agentfiles")
                self.assertIsNone(claim, "{} claimed its own existence".format(output))

    def test_other_agent_files_are_still_reported(self):
        root = self.fixture(
            {"package.json": '{"name":"x"}', "CLAUDE.md": "# c\n", "AGENTS.md": "# a\n"}
        )
        a = analyze(root, output_name="CLAUDE.md")
        text = a.by_id("repo.agentfiles").text
        self.assertIn("AGENTS.md", text)
        self.assertNotIn("CLAUDE.md", text)

    def test_absent_directory_yields_no_layout_claim(self):
        root = self.fixture({"package.json": '{"name":"x"}'})
        a = analyze(root)
        self.assertIsNone(a.by_id("repo.layout.src"))
        self.assertIn("repo.layout.tests", [p.id for p in a.probes])


class TestRender(RepoCase):
    def test_every_claim_carries_evidence(self):
        root = self.fixture({"package.json": '{"name":"x","scripts":{"test":"y"}}'})
        for claim in analyze(root).claims:
            self.assertTrue(claim.evidence, "{} has no evidence".format(claim.id))

    def test_inferred_claims_are_marked_in_the_output(self):
        root = self.fixture(
            {
                "pom.xml": "<project><artifactId>x</artifactId></project>",
                "src/test/java/T.java": "class T {}\n",
            }
        )
        md = render_agents_md(analyze(root), version="0.1.0")
        self.assertIn("_(inferred)_", md)
        self.assertIn(BEGIN, md)
        self.assertIn(END, md)

    def test_hand_written_content_survives_regeneration(self):
        root = self.fixture({"package.json": '{"name":"x"}'})
        a = analyze(root)
        first = render_agents_md(a, version="0.1.0")
        edited = first + "\n## Hand-written\n\nDo not lose me.\n"
        second = render_agents_md(a, version="0.1.0", previous=edited)
        self.assertIn("Do not lose me.", second)
        self.assertEqual(second.count(BEGIN), 1)

    def test_unmanaged_existing_file_is_kept_below_the_block(self):
        root = self.fixture({"package.json": '{"name":"x"}'})
        out = render_agents_md(
            analyze(root), version="0.1.0", previous="# My own notes\n\nkeep this\n"
        )
        self.assertIn("keep this", out)
        self.assertLess(out.index(BEGIN), out.index("keep this"))

    def test_report_names_the_evidence(self):
        root = self.fixture({"package.json": '{"name":"x","scripts":{"test":"pytest"}}'})
        text = render_report(analyze(root))
        self.assertIn("package.json -> scripts.test", text)


class TestDrift(RepoCase):
    def test_renamed_script_is_reported_as_changed(self):
        before = analyze(self.fixture({"package.json": '{"name":"x","scripts":{"test":"jest"}}'}))
        after = analyze(self.fixture({"package.json": '{"name":"x","scripts":{"test":"vitest"}}'}))
        diff = diff_state(build_state(before, "0.1.0"), build_state(after, "0.1.0"))
        self.assertTrue(has_drift(diff))
        self.assertEqual([c["id"] for c in diff["changed"]], ["node.script.test"])

    def test_deleted_directory_is_reported_as_removed(self):
        before = analyze(self.fixture({"package.json": '{"name":"x"}', "src/i.js": ""}))
        after = analyze(self.fixture({"package.json": '{"name":"x"}'}))
        diff = diff_state(build_state(before, "0.1.0"), build_state(after, "0.1.0"))
        self.assertIn("repo.layout.src", diff["removed"])

    def test_unchanged_repository_reports_no_drift(self):
        files = {"package.json": '{"name":"x","scripts":{"build":"tsc"}}', "src/i.js": ""}
        diff = diff_state(
            build_state(analyze(self.fixture(files)), "0.1.0"),
            build_state(analyze(self.fixture(files)), "0.1.0"),
        )
        self.assertFalse(has_drift(diff))


class TestDeterminism(RepoCase):
    """The output must not depend on the machine, the run, or the caller.

    This is the property that makes the tool usable as a shared source of truth
    across agents and model versions: two runs cannot disagree.
    """

    FILES = {
        "package.json": json.dumps(
            {"name": "d", "scripts": {"test": "t", "build": "b", "zzz": "z", "aaa": "a"}}
        ),
        "pom.xml": "<project><artifactId>d</artifactId></project>",
        "Makefile": ".PHONY: b a c\n",
        ".github/workflows/b.yml": "name: b\n",
        ".github/workflows/a.yml": "name: a\n",
        "src/x.js": "",
        "tests/y.js": "",
    }

    def test_two_runs_over_the_same_tree_are_byte_identical(self):
        root = self.fixture(self.FILES)
        first = render_agents_md(analyze(root), version="0.1.0")
        second = render_agents_md(analyze(root), version="0.1.0")
        self.assertEqual(first, second)

    def test_two_identical_trees_in_different_locations_agree(self):
        a = render_agents_md(analyze(self.fixture(self.FILES)), version="0.1.0")
        b = render_agents_md(analyze(self.fixture(self.FILES)), version="0.1.0")
        self.assertEqual(a, b)

    def test_state_file_is_stable_across_runs(self):
        root = self.fixture(self.FILES)
        first = json.dumps(build_state(analyze(root), "0.1.0"), sort_keys=True)
        second = json.dumps(build_state(analyze(root), "0.1.0"), sort_keys=True)
        self.assertEqual(first, second)

    def test_claim_order_does_not_depend_on_insertion_order(self):
        root = self.fixture(self.FILES)
        ids = [c.id for c in analyze(root).claims]
        self.assertEqual(ids, [c.id for c in analyze(root).claims])
        sections = [c.section for c in analyze(root).claims]
        # Sections must appear in canonical order, never interleaved.
        first_index = {s: sections.index(s) for s in dict.fromkeys(sections)}
        self.assertEqual(list(first_index), sorted(first_index, key=first_index.get))


class TestCli(RepoCase):
    def test_refuses_to_write_when_nothing_is_provable(self):
        root = self.fixture({"README.md": "hi\n"})
        self.assertEqual(main([root]), 2)
        self.assertFalse(os.path.exists(os.path.join(root, "CLAUDE.md")))

    def test_write_then_check_reports_no_drift(self):
        root = self.fixture({"package.json": '{"name":"x","scripts":{"test":"t"}}'})
        self.assertEqual(main([root]), 0)
        self.assertTrue(os.path.exists(os.path.join(root, "CLAUDE.md")))
        self.assertEqual(main([root, "--check"]), 0)

    def test_check_fails_after_the_repository_changes(self):
        root = self.fixture({"package.json": '{"name":"x","scripts":{"test":"jest"}}'})
        self.assertEqual(main([root]), 0)
        with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as fh:
            fh.write('{"name":"x","scripts":{"test":"vitest"}}')
        self.assertEqual(main([root, "--check"]), 1)

    def test_generation_is_idempotent(self):
        """Writing the file must not change what the next run observes.

        Regression: an earlier build listed the output file among the "other
        agent instruction files", so generating it created a new claim and the
        very next --check reported drift against an untouched repository.
        """
        root = self.fixture({"package.json": '{"name":"x","scripts":{"test":"t"}}'})
        out = os.path.join(root, "CLAUDE.md")

        self.assertEqual(main([root]), 0)
        with open(out, encoding="utf-8") as fh:
            first = fh.read()
        self.assertEqual(main([root]), 0)
        with open(out, encoding="utf-8") as fh:
            second = fh.read()

        self.assertEqual(first, second)
        self.assertEqual(main([root, "--check"]), 0)

    def test_out_flag_renames_the_file_and_stays_idempotent(self):
        root = self.fixture({"package.json": '{"name":"x"}'})
        self.assertEqual(main([root, "--out", "AGENTS.md"]), 0)
        out = os.path.join(root, "AGENTS.md")
        self.assertTrue(os.path.exists(out))
        self.assertFalse(os.path.exists(os.path.join(root, "CLAUDE.md")))
        with open(out, encoding="utf-8") as fh:
            self.assertIn("# AGENTS.md", fh.read())
        self.assertEqual(main([root, "--out", "AGENTS.md", "--check"]), 0)

    def test_check_without_a_baseline_is_an_error(self):
        root = self.fixture({"package.json": '{"name":"x"}'})
        self.assertEqual(main([root, "--check"]), 2)

    def test_report_and_json_write_nothing(self):
        root = self.fixture({"package.json": '{"name":"x"}'})
        self.assertEqual(main([root, "--report"]), 0)
        self.assertEqual(main([root, "--json"]), 0)
        self.assertFalse(os.path.exists(os.path.join(root, "CLAUDE.md")))


class TestSupersedes(RepoCase):
    """A specific claim must silence the generic one that contradicts it."""

    def test_java_test_layout_silences_the_generic_missing_tests_probe(self):
        """Regression: the file said "tests live in src/test/java" and, three
        lines later, "test dirs: checked for, absent". Both were true of their
        own detector and together they read as a contradiction."""
        root = self.fixture(
            {
                "pom.xml": "<project><artifactId>x</artifactId></project>",
                "src/test/java/T.java": "class T {}\n",
                "src/main/java/A.java": "class A {}\n",
            }
        )
        a = analyze(root)
        self.assertIsNotNone(a.by_id("java.layout.src.test.java"))
        self.assertNotIn("repo.layout.tests", [p.id for p in a.probes])

    def test_java_source_layout_silences_the_generic_src_claim(self):
        root = self.fixture(
            {
                "pom.xml": "<project><artifactId>x</artifactId></project>",
                "src/main/java/A.java": "class A {}\n",
            }
        )
        a = analyze(root)
        self.assertIsNotNone(a.by_id("java.layout.src.main.java"))
        self.assertIsNone(a.by_id("repo.layout.src"))

    def test_a_non_java_project_still_gets_the_generic_claims(self):
        root = self.fixture({"package.json": '{"name":"x"}', "src/i.js": "", "tests/t.js": ""})
        a = analyze(root)
        self.assertIsNotNone(a.by_id("repo.layout.src"))
        self.assertIsNotNone(a.by_id("repo.layout.tests"))


class TestNonAsciiOutput(RepoCase):
    """Real manifests carry non-ASCII text; the tool must survive printing it."""

    KOREAN = "개발 학습 노트 (CS·ML) VitePress 사이트"

    def test_written_file_keeps_non_ascii_intact(self):
        root = self.fixture(
            {"package.json": json.dumps({"name": "x", "description": self.KOREAN})}
        )
        self.assertEqual(main([root]), 0)
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8") as fh:
            self.assertIn(self.KOREAN, fh.read())

    def test_report_does_not_crash_on_a_legacy_console_code_page(self):
        """Regression: --report died with UnicodeEncodeError under cp1252.

        Reproduced by running the CLI in a subprocess whose stdio encoding is a
        legacy Windows code page that cannot represent Korean. Before the fix
        this exited 1 with a traceback.
        """
        root = self.fixture(
            {"package.json": json.dumps({"name": "x", "description": self.KOREAN})}
        )
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=repo)

        result = subprocess.run(
            [sys.executable, "-m", "verified_init", "--report", root],
            capture_output=True,
            env=env,
            cwd=repo,
        )
        self.assertEqual(
            result.returncode,
            0,
            "CLI crashed under cp1252: {}".format(result.stderr.decode("utf-8", "replace")),
        )


class TestFrameworks(RepoCase):
    """Stack detection reads declared dependencies, so it stays VERIFIED."""

    def test_node_stack_and_test_runner_from_dependencies(self):
        root = self.fixture(
            {
                "package.json": json.dumps(
                    {
                        "name": "site",
                        "description": "docs site",
                        "license": "MIT",
                        "devDependencies": {"vitepress": "^1.6.3", "vitest": "^2.0.0"},
                    }
                )
            }
        )
        a = analyze(root)
        self.assertIn("VitePress", a.by_id("node.stack").text)
        self.assertIn("Vitest", a.by_id("node.testframework").text)
        self.assertEqual(a.by_id("node.description").text, "docs site")
        self.assertIn("MIT", a.by_id("node.license").text)

    def test_unrecognised_dependencies_produce_no_stack_claim(self):
        """A wrong stack label is worse than a missing one."""
        root = self.fixture(
            {"package.json": json.dumps({"name": "x", "dependencies": {"left-pad": "1.0.0"}})}
        )
        self.assertIsNone(analyze(root).by_id("node.stack"))

    def test_stack_labels_are_sorted_for_determinism(self):
        root = self.fixture(
            {
                "package.json": json.dumps(
                    {"name": "x", "dependencies": {"vue": "3", "astro": "4", "react": "18"}}
                )
            }
        )
        text = analyze(root).by_id("node.stack").text
        self.assertIn("Astro, React, Vue", text)

    def test_java_maven_stack_and_test_stack(self):
        root = self.fixture(
            {
                "pom.xml": (
                    "<project><artifactId>parking-api</artifactId><dependencies>"
                    "<dependency><artifactId>spring-boot-starter-web</artifactId></dependency>"
                    "<dependency><artifactId>lombok</artifactId></dependency>"
                    "<dependency><artifactId>spring-boot-starter-test</artifactId></dependency>"
                    "</dependencies></project>"
                )
            }
        )
        a = analyze(root)
        self.assertIn("Spring Boot Web (MVC)", a.by_id("java.maven.stack").text)
        self.assertIn("Lombok", a.by_id("java.maven.stack").text)
        self.assertIn("Spring Boot Test", a.by_id("java.maven.testframework").text)

    def test_java_gradle_stack_from_coordinates(self):
        root = self.fixture(
            {
                "build.gradle.kts": (
                    'implementation("org.springframework.boot:spring-boot-starter-webflux")\n'
                    "implementation('io.micronaut:micronaut-core:4.0.0')\n"
                )
            }
        )
        self.assertIn("Spring WebFlux", analyze(root).by_id("java.gradle.stack").text)

    def test_python_extras_do_not_truncate_the_dependency_array(self):
        """Regression: a `[` inside a requirement ended the array scan early.

        `sqlalchemy[asyncio]` made a non-greedy regex stop at the extras
        bracket, silently discarding every dependency declared after it.
        """
        root = self.fixture(
            {
                "pyproject.toml": (
                    "[project]\nname = 's'\n"
                    'dependencies = ["fastapi>=0.110", "sqlalchemy[asyncio]==2.0", "pytest>=8"]\n'
                )
            }
        )
        a = analyze(root)
        stack = a.by_id("py.stack").text
        self.assertIn("FastAPI", stack)
        self.assertIn("SQLAlchemy", stack)
        self.assertIn("pytest", a.by_id("py.testframework").text)

    def test_python_multiline_dependency_array(self):
        root = self.fixture(
            {
                "pyproject.toml": (
                    "[project]\nname = 's'\ndependencies = [\n"
                    '  "django>=5",\n  "celery[redis]>=5",\n]\n'
                )
            }
        )
        stack = analyze(root).by_id("py.stack").text
        self.assertIn("Django", stack)
        self.assertIn("Celery", stack)

    def test_go_stack_matches_versioned_module_paths(self):
        root = self.fixture(
            {
                "go.mod": (
                    "module github.com/me/api\n\ngo 1.22\n\nrequire (\n"
                    "\tgithub.com/gin-gonic/gin v1.9.1\n\tgorm.io/gorm v1.25.0\n)\n"
                )
            }
        )
        stack = analyze(root).by_id("go.stack").text
        self.assertIn("Gin", stack)
        self.assertIn("GORM", stack)

    def test_rust_stack_from_dependencies_table_only(self):
        root = self.fixture(
            {
                "Cargo.toml": (
                    '[package]\nname = "s"\nedition = "2021"\n\n'
                    '[dependencies]\naxum = "0.7"\ntokio = { version = "1" }\n\n'
                    '[dev-dependencies]\nrocket = "0.5"\n'
                )
            }
        )
        stack = analyze(root).by_id("rust.stack").text
        self.assertIn("Axum", stack)
        self.assertIn("Tokio", stack)
        self.assertNotIn("Rocket", stack, "dev-dependencies must not be read as the stack")

    def test_python_requirement_normalisation(self):
        cases = {
            "Django>=4.2": "django",
            "uvicorn[standard]==0.30.1": "uvicorn",
            "  Flask  ": "flask",
            "typing_extensions": "typing-extensions",
            "# a comment": "",
            "-r base.txt": "",
            "": "",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(frameworks.normalise_python_requirement(raw), expected)


class TestSkillPackaging(unittest.TestCase):
    """Guards the Claude Code skill directory.

    The skill is just files on disk, so nothing else would notice if one of
    them moved and the runner stopped resolving the package.
    """

    REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SKILL = os.path.join(REPO, "skills", "verified-init")

    def test_skill_files_are_where_the_docs_say(self):
        self.assertTrue(os.path.isfile(os.path.join(self.SKILL, "SKILL.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.SKILL, "scripts", "run.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.REPO, ".claude-plugin", "plugin.json")))

    def test_skill_frontmatter_declares_name_and_description(self):
        with open(os.path.join(self.SKILL, "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.startswith("---\n"), "SKILL.md must open with YAML frontmatter")
        frontmatter = text.split("---\n", 2)[1]
        self.assertIn("name: verified-init", frontmatter)
        self.assertIn("description:", frontmatter)

    def test_runner_resolves_the_package_from_its_own_location(self):
        """run.py walks up three levels; this fails the moment that stops holding."""
        runner = os.path.join(self.SKILL, "scripts", "run.py")
        resolved = os.path.abspath(os.path.join(os.path.dirname(runner), "..", "..", ".."))
        self.assertEqual(resolved, self.REPO)
        self.assertTrue(os.path.isdir(os.path.join(resolved, "verified_init")))

    def test_plugin_manifest_is_valid_json_with_a_version(self):
        with open(os.path.join(self.REPO, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["name"], "verified-init")
        self.assertTrue(manifest["version"])
        self.assertTrue(manifest["description"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
