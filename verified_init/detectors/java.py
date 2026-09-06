"""Java: Maven and Gradle.

Build files are parsed with targeted regexes rather than a full XML/Groovy
parser. That is deliberate: this tool must run with the standard library only,
and it must never evaluate a build script. A pattern that does not match
produces a probe ("looked for, absent"), never a guess.
"""

from __future__ import annotations

import re

from .. import frameworks
from ..claims import Claim, Probe, INFERRED, VERIFIED
from ..fsx import exists, first_existing, is_dir, read_text

ID = "java"

_MODULE_RE = re.compile(r"<module>\s*([^<]+?)\s*</module>")
_TOOLCHAIN_RE = re.compile(r"JavaLanguageVersion\.of\((\d+)\)")
_COMPAT_RE = re.compile(
    r"(?:sourceCompatibility|targetCompatibility)\s*=?\s*"
    r"['\"]?(?:JavaVersion\.VERSION_)?([\d._]+)['\"]?"
)
_INCLUDE_RE = re.compile(r"include\s*\(?\s*['\"]:?([^'\"]+)['\"]")
_ARTIFACT_RE = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>")
#: Gradle coordinates: implementation("group:artifact:version") or the
#: single-quoted Groovy form. Only the artifact segment is needed.
_GRADLE_DEP_RE = re.compile(r"['\"][\w.\-]+:([\w.\-]+)(?::[^'\"]*)?['\"]")


def _stack_claims(prefix, artifacts, source, claims):
    """Turn declared artifact ids into stack and test-framework claims."""
    stack = frameworks.match(artifacts, frameworks.JAVA)
    if stack:
        claims.append(
            Claim(
                id="{}.stack".format(prefix),
                section="Project",
                text="Built on {}.".format(", ".join(stack)),
                status=VERIFIED,
                evidence="{} -> declared dependencies".format(source),
            )
        )
    runners = frameworks.match(artifacts, frameworks.JAVA_TEST)
    if runners:
        claims.append(
            Claim(
                id="{}.testframework".format(prefix),
                section="Build & Test",
                text="Test stack: {}.".format(", ".join(runners)),
                status=VERIFIED,
                evidence="{} -> declared dependencies".format(source),
            )
        )

#: Standard layout directories. Present-but-undeclared, hence INFERRED.
STANDARD_LAYOUT = [
    ("src/main/java", "Production sources"),
    ("src/test/java", "Tests"),
    ("src/main/resources", "Resources"),
]


def _xml_tag(xml: str, name: str):
    """Text of the first ``<name>...</name>``, or ``None``."""
    match = re.search(r"<{0}>\s*([^<]+?)\s*</{0}>".format(re.escape(name)), xml)
    return match.group(1) if match else None


def _detect_maven(root, claims, probes):
    pom = read_text(root, "pom.xml")
    if pom is None:
        return False

    artifact = _xml_tag(pom, "artifactId")
    if artifact:
        claims.append(
            Claim(
                id="java.maven.artifact",
                section="Project",
                text="Maven project `{}`.".format(artifact),
                status=VERIFIED,
                evidence="pom.xml -> <artifactId>",
            )
        )

    level = (
        _xml_tag(pom, "maven.compiler.release")
        or _xml_tag(pom, "maven.compiler.source")
        or _xml_tag(pom, "java.version")
    )
    if level:
        claims.append(
            Claim(
                id="java.version",
                section="Setup",
                text="Targets Java {}.".format(level),
                status=VERIFIED,
                evidence="pom.xml -> Java level property = {}".format(level),
            )
        )
    else:
        probes.append(
            Probe(
                id="java.version",
                looked_for=(
                    "pom.xml -> maven.compiler.release / maven.compiler.source / java.version"
                ),
            )
        )

    has_wrapper = exists(root, "mvnw") or exists(root, "mvnw.cmd")
    cmd = "./mvnw" if has_wrapper else "mvn"
    if has_wrapper:
        claims.append(
            Claim(
                id="java.maven.wrapper",
                section="Setup",
                text="Use the bundled Maven wrapper (`./mvnw`); no system Maven required.",
                status=VERIFIED,
                evidence="mvnw present",
            )
        )

    for suffix, goal, label in (("build", "package", "Build"), ("test", "test", "Run tests")):
        claims.append(
            Claim(
                id="java.maven.{}".format(suffix),
                section="Build & Test",
                text="{} with `{} {}`.".format(label, cmd, goal),
                status=VERIFIED,
                evidence="pom.xml present (standard Maven lifecycle)",
            )
        )

    _stack_claims("java.maven", set(_ARTIFACT_RE.findall(pom)), "pom.xml", claims)

    modules = _MODULE_RE.findall(pom)
    if modules:
        listed = ", ".join("`{}`".format(m) for m in modules)
        claims.append(
            Claim(
                id="java.maven.modules",
                section="Layout",
                text="Multi-module build. Modules: {}.".format(listed),
                status=VERIFIED,
                evidence="pom.xml -> {} <module> entries".format(len(modules)),
            )
        )

    return True


def _detect_gradle(root, claims, probes):
    build_file = first_existing(root, ["build.gradle.kts", "build.gradle"])
    settings_file = first_existing(root, ["settings.gradle.kts", "settings.gradle"])
    if not build_file and not settings_file:
        return False

    has_wrapper = exists(root, "gradlew") or exists(root, "gradlew.bat")
    cmd = "./gradlew" if has_wrapper else "gradle"
    if has_wrapper:
        claims.append(
            Claim(
                id="java.gradle.wrapper",
                section="Setup",
                text="Use the bundled Gradle wrapper (`./gradlew`); no system Gradle required.",
                status=VERIFIED,
                evidence="gradlew present",
            )
        )

    source = build_file or settings_file
    for suffix, task, label in (("build", "build", "Build"), ("test", "test", "Run tests")):
        claims.append(
            Claim(
                id="java.gradle.{}".format(suffix),
                section="Build & Test",
                text="{} with `{} {}`.".format(label, cmd, task),
                status=VERIFIED,
                evidence="{} present".format(source),
            )
        )

    build = read_text(root, build_file) or "" if build_file else ""
    toolchain = _TOOLCHAIN_RE.search(build)
    compat = _COMPAT_RE.search(build)
    level = toolchain.group(1) if toolchain else (compat.group(1).replace("_", ".") if compat else None)
    if level:
        claims.append(
            Claim(
                id="java.version",
                section="Setup",
                text="Targets Java {}.".format(level),
                status=VERIFIED,
                evidence="{} -> toolchain/sourceCompatibility".format(build_file),
            )
        )
    else:
        probes.append(
            Probe(
                id="java.version",
                looked_for="JavaLanguageVersion.of(N) or sourceCompatibility in the Gradle build file",
            )
        )

    _stack_claims("java.gradle", set(_GRADLE_DEP_RE.findall(build)), build_file, claims)

    settings = read_text(root, settings_file) or "" if settings_file else ""
    includes = _INCLUDE_RE.findall(settings)
    if includes:
        listed = ", ".join("`{}`".format(m) for m in includes)
        claims.append(
            Claim(
                id="java.gradle.modules",
                section="Layout",
                text="Multi-project build. Subprojects: {}.".format(listed),
                status=VERIFIED,
                evidence="{} -> {} include() entries".format(settings_file, len(includes)),
            )
        )

    return True


def detect(root, ctx):
    claims = []
    probes = []

    is_maven = _detect_maven(root, claims, probes)
    is_gradle = _detect_gradle(root, claims, probes)
    if not is_maven and not is_gradle:
        return None

    for directory, label in STANDARD_LAYOUT:
        claim_id = "java.layout.{}".format(directory.replace("/", "."))
        if is_dir(root, directory):
            claims.append(
                Claim(
                    id=claim_id,
                    section="Layout",
                    text="{} live in `{}/`.".format(label, directory),
                    status=INFERRED,
                    evidence=(
                        "{}/ exists (standard Maven/Gradle layout, "
                        "not declared in the build file)".format(directory)
                    ),
                )
            )
        else:
            probes.append(Probe(id=claim_id, looked_for="{}/".format(directory)))

    return claims, probes
