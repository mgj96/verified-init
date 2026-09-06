"""Recognising a project's stack from its declared dependencies.

"This is a VitePress site" is the single most useful sentence you can put in
front of an agent, and it is not a guess: the dependency is declared in a
manifest the project maintains. This module turns declared dependency names
into that sentence, and nothing else -- an unrecognised dependency is simply
not reported.

Mappings are deliberately narrow. A wrong stack label is worse than a missing
one, so only unambiguous, widely used packages appear here.
"""

from __future__ import annotations

import re

#: Package name -> human label. Node (npm) ecosystem.
NODE = {
    "@angular/core": "Angular",
    "@nestjs/core": "NestJS",
    "@remix-run/react": "Remix",
    "@sveltejs/kit": "SvelteKit",
    "astro": "Astro",
    "electron": "Electron",
    "express": "Express",
    "fastify": "Fastify",
    "gatsby": "Gatsby",
    "hono": "Hono",
    "koa": "Koa",
    "next": "Next.js",
    "nuxt": "Nuxt",
    "react": "React",
    "svelte": "Svelte",
    "vite": "Vite",
    "vitepress": "VitePress",
    "vue": "Vue",
    "vuepress": "VuePress",
}

#: Test runners are called out separately: knowing how to run the tests is a
#: different question from knowing what the project is.
NODE_TEST = {
    "@playwright/test": "Playwright",
    "ava": "AVA",
    "cypress": "Cypress",
    "jasmine": "Jasmine",
    "jest": "Jest",
    "mocha": "Mocha",
    "vitest": "Vitest",
}

PYTHON = {
    "aiohttp": "aiohttp",
    "celery": "Celery",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "litestar": "Litestar",
    "pandas": "pandas",
    "pydantic": "Pydantic",
    "scrapy": "Scrapy",
    "sqlalchemy": "SQLAlchemy",
    "starlette": "Starlette",
    "streamlit": "Streamlit",
    "torch": "PyTorch",
}

PYTHON_TEST = {"nose2": "nose2", "pytest": "pytest", "tox": "tox"}

#: Maven/Gradle artifactIds. Matched on the artifact, not the group, because
#: Gradle coordinates and Maven <artifactId> agree on that segment.
JAVA = {
    "hibernate-core": "Hibernate",
    "jackson-databind": "Jackson",
    "lombok": "Lombok",
    "mapstruct": "MapStruct",
    "micronaut-core": "Micronaut",
    "mybatis": "MyBatis",
    "quarkus-core": "Quarkus",
    "spring-boot-starter": "Spring Boot",
    "spring-boot-starter-batch": "Spring Batch",
    "spring-boot-starter-data-jpa": "Spring Data JPA",
    "spring-boot-starter-security": "Spring Security",
    "spring-boot-starter-web": "Spring Boot Web (MVC)",
    "spring-boot-starter-webflux": "Spring WebFlux",
    "querydsl-jpa": "Querydsl",
}

JAVA_TEST = {
    "assertj-core": "AssertJ",
    "junit-jupiter": "JUnit 5",
    "junit": "JUnit 4",
    "mockito-core": "Mockito",
    "spring-boot-starter-test": "Spring Boot Test",
    "testcontainers": "Testcontainers",
}

RUST = {
    "actix-web": "Actix Web",
    "axum": "Axum",
    "bevy": "Bevy",
    "clap": "clap",
    "diesel": "Diesel",
    "rocket": "Rocket",
    "serde": "Serde",
    "sqlx": "SQLx",
    "tokio": "Tokio",
}

#: Go module paths are matched by suffix, since they are fully qualified.
GO = {
    "github.com/gin-gonic/gin": "Gin",
    "github.com/gofiber/fiber": "Fiber",
    "github.com/labstack/echo": "Echo",
    "github.com/spf13/cobra": "Cobra",
    "github.com/stretchr/testify": "testify",
    "gorm.io/gorm": "GORM",
}

#: Strips version specifiers and extras: "uvicorn[standard]>=0.30" -> "uvicorn".
_PY_REQUIREMENT = re.compile(r"^([A-Za-z0-9._-]+)")


def normalise_python_requirement(raw: str) -> str:
    """Package name from a PEP 508 requirement string, lowercased.

    Returns an empty string for comments, blank lines and pip flags such as
    ``-r base.txt``, which are not requirements at all.
    """
    text = raw.strip()
    if not text or text.startswith("#") or text.startswith("-"):
        return ""
    match = _PY_REQUIREMENT.match(text)
    return match.group(1).lower().replace("_", "-") if match else ""


def match(declared, table):
    """Labels for every declared dependency present in ``table``.

    Args:
        declared: Iterable of dependency names as the manifest declares them.
        table: One of the mappings above.

    Returns:
        Sorted, de-duplicated labels. Sorted because the generated file must be
        byte-identical across runs, and manifest ordering is not stable.
    """
    found = {table[name] for name in declared if name in table}
    return sorted(found)


def match_prefix(declared, table):
    """Like :func:`match`, but a declared value need only start with the key.

    Go module paths carry a major-version suffix (``/v2``), so exact matching
    would miss them.
    """
    found = set()
    for name in declared:
        for key, label in table.items():
            if name == key or name.startswith(key + "/"):
                found.add(label)
    return sorted(found)
