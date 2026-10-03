#!/usr/bin/env python3
"""Validate the static support hub without third-party packages."""

from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SITE_ORIGIN = "https://sebastianrodriguez-dev.github.io"
PLACEHOLDER = "SUPPORT_" + "EMAIL_PENDING"
PLACEHOLDER_FILES = {
    Path("apps/all-four-in-place/support/index.html"),
    Path("apps/all-four-in-place/privacy/index.html"),
}
EXPECTED_HTML = {
    Path("index.html"),
    Path("404.html"),
    Path("apps/all-four-in-place/index.html"),
    Path("apps/all-four-in-place/support/index.html"),
    Path("apps/all-four-in-place/privacy/index.html"),
    Path("apps/all-four-in-place/accessibility/index.html"),
    Path("apps/nookshift/index.html"),
    Path("apps/nookshift/support/index.html"),
    Path("apps/nookshift/privacy/index.html"),
}
FORBIDDEN_ELEMENTS = {
    "applet",
    "audio",
    "embed",
    "form",
    "iframe",
    "object",
    "script",
    "source",
    "style",
    "video",
}
REQUIRED_CSP = (
    "default-src 'none'; style-src 'self'; img-src 'self' data:; "
    "font-src 'none'; script-src 'none'; connect-src 'none'; "
    "object-src 'none'; frame-src 'none'; media-src 'none'; "
    "worker-src 'none'; child-src 'none'; manifest-src 'none'; "
    "base-uri 'none'; form-action 'none'; upgrade-insecure-requests"
)


class PageParser(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.path = path
        self.errors: list[str] = []
        self.links: list[tuple[str, str, str]] = []
        self.ids: set[str] = set()
        self.h1_count = 0
        self.main_count = 0
        self.html_lang: str | None = None
        self.title_depth = 0
        self.title_text = ""
        self.csp_values: list[str] = []
        self.referrer_values: list[str] = []
        self.canonical_values: list[str] = []
        self.stylesheet_values: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {name.lower(): value or "" for name, value in attrs_list}

        if tag in FORBIDDEN_ELEMENTS:
            self.errors.append(f"forbidden <{tag}> element")
        if "style" in attrs:
            self.errors.append(f"inline style on <{tag}>")
        for name in attrs:
            if name.startswith("on"):
                self.errors.append(f"event-handler attribute {name} on <{tag}>")

        element_id = attrs.get("id")
        if element_id:
            if element_id in self.ids:
                self.errors.append(f"duplicate id #{element_id}")
            self.ids.add(element_id)

        if tag == "html":
            self.html_lang = attrs.get("lang")
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "title":
            self.title_depth += 1
        elif tag == "meta":
            if attrs.get("http-equiv", "").lower() == "content-security-policy":
                self.csp_values.append(attrs.get("content", ""))
            if attrs.get("name", "").lower() == "referrer":
                self.referrer_values.append(attrs.get("content", ""))
        elif tag == "link":
            relation = attrs.get("rel", "").lower()
            href = attrs.get("href", "")
            if relation == "canonical":
                self.canonical_values.append(href)
            elif relation == "stylesheet":
                self.stylesheet_values.append(href)
            else:
                self.errors.append(f"unsupported link relation {relation or '(missing)'}")

        for attribute in ("href", "src"):
            value = attrs.get(attribute)
            if value:
                self.links.append((tag, attribute, value))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_text += data


def expected_url(path: Path) -> str:
    if path == Path("index.html"):
        return f"{SITE_ORIGIN}/"
    if path.name == "index.html":
        return f"{SITE_ORIGIN}/{path.parent.as_posix()}/"
    return f"{SITE_ORIGIN}/{path.as_posix()}"


def internal_target(url: str) -> tuple[Path | None, str | None]:
    parts = urlsplit(url)
    if parts.scheme and (parts.scheme != "https" or parts.netloc != "sebastianrodriguez-dev.github.io"):
        return None, parts.fragment or None
    if parts.query:
        raise ValueError("internal links must not contain query strings")

    raw_path = unquote(parts.path)
    if not raw_path:
        raw_path = "/"
    if ".." in Path(raw_path).parts:
        raise ValueError("path traversal is not allowed")
    relative = Path(raw_path.removeprefix("/"))
    if raw_path.endswith("/"):
        relative /= "index.html"
    return relative, parts.fragment or None


def scan_page(path: Path, all_ids: dict[Path, set[str]]) -> list[str]:
    errors: list[str] = []
    text = (ROOT / path).read_text(encoding="utf-8")
    if not text.lower().startswith("<!doctype html>"):
        errors.append("missing HTML5 doctype")

    parser = PageParser(path)
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:  # HTMLParser errors are rare but must fail closed.
        errors.append(f"HTML parser error: {exc}")
        return errors

    errors.extend(parser.errors)
    if parser.html_lang != "en":
        errors.append("html lang must be en")
    if parser.h1_count != 1:
        errors.append(f"expected one h1, found {parser.h1_count}")
    if parser.main_count != 1:
        errors.append(f"expected one main, found {parser.main_count}")
    if not parser.title_text.strip():
        errors.append("missing non-empty title")
    if parser.csp_values != [REQUIRED_CSP]:
        errors.append("Content Security Policy is missing or differs from the approved policy")
    if parser.referrer_values != ["no-referrer"]:
        errors.append("referrer policy must be no-referrer")
    if parser.canonical_values != [expected_url(path)]:
        errors.append(f"canonical URL must be {expected_url(path)}")
    stylesheet = (
        "apps/all-four-in-place/assets/site.css"
        if path.is_relative_to("apps/all-four-in-place")
        else "assets/site.css"
    )
    if parser.stylesheet_values != [f"{SITE_ORIGIN}/{stylesheet}"]:
        errors.append("page must load only its approved first-party stylesheet")

    for tag, attribute, url in parser.links:
        if url.startswith("mailto:"):
            address = url.removeprefix("mailto:")
            if not address or (address != PLACEHOLDER and "@" not in address):
                errors.append(f"invalid mailto link {url!r}")
            continue
        if url.startswith("#"):
            fragment = unquote(url[1:])
            if fragment not in parser.ids:
                errors.append(f"missing local fragment target #{fragment}")
            continue

        parts = urlsplit(url)
        if parts.scheme and parts.scheme != "https":
            errors.append(f"non-HTTPS link {url!r}")
            continue

        is_resource = attribute == "src" or (tag == "link" and url not in parser.canonical_values)
        if is_resource and not url.startswith(f"{SITE_ORIGIN}/"):
            errors.append(f"third-party or relative resource {url!r}")
            continue
        if parts.scheme == "https" and parts.netloc != "sebastianrodriguez-dev.github.io":
            if tag != "a":
                errors.append(f"third-party resource {url!r}")
            continue

        try:
            target, fragment = internal_target(url)
        except ValueError as exc:
            errors.append(f"invalid internal link {url!r}: {exc}")
            continue
        if target is None or not (ROOT / target).is_file():
            errors.append(f"broken internal link {url!r}")
            continue
        if fragment and fragment not in all_ids.get(target, set()):
            errors.append(f"missing fragment #{fragment} in {target}")

    return errors


def parse_ids(paths: set[Path]) -> dict[Path, set[str]]:
    result: dict[Path, set[str]] = {}
    for path in paths:
        parser = PageParser(path)
        parser.feed((ROOT / path).read_text(encoding="utf-8"))
        parser.close()
        result[path] = parser.ids
    return result


def scan_placeholders(allow_placeholders: bool) -> list[str]:
    errors: list[str] = []
    locations: set[Path] = set()
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if PLACEHOLDER in text:
            locations.add(path.relative_to(ROOT))

    unexpected = locations - PLACEHOLDER_FILES
    if unexpected:
        errors.append("contact placeholder appears outside approved All Four contact pages: " + ", ".join(map(str, sorted(unexpected))))
    if locations and not allow_placeholders:
        errors.append("All Four in Place needs a monitored support email before deployment")
    return errors


def scan_css() -> list[str]:
    errors: list[str] = []
    for path in ("assets/site.css", "apps/all-four-in-place/assets/site.css"):
        css = (ROOT / path).read_text(encoding="utf-8").lower()
        for forbidden in ("@import", "url(", "expression(", "javascript:"):
            if forbidden in css:
                errors.append(f"{path} contains forbidden construct {forbidden}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="run structural checks while a documented contact placeholder remains",
    )
    args = parser.parse_args()

    errors: list[str] = []
    actual_html = {path.relative_to(ROOT) for path in ROOT.rglob("*.html") if ".git" not in path.parts}
    missing = EXPECTED_HTML - actual_html
    extra = actual_html - EXPECTED_HTML
    if missing:
        errors.append("missing required HTML: " + ", ".join(map(str, sorted(missing))))
    if extra:
        errors.append("unexpected HTML: " + ", ".join(map(str, sorted(extra))))

    existing = EXPECTED_HTML & actual_html
    ids = parse_ids(existing)
    for path in sorted(existing):
        errors.extend(f"{path}: {message}" for message in scan_page(path, ids))
    errors.extend(scan_placeholders(args.allow_placeholders))
    errors.extend(scan_css())

    if errors:
        print("Validation failed:", file=sys.stderr)
        for message in errors:
            print(f"- {message}", file=sys.stderr)
        return 1

    qualifier = " (contact placeholder allowed for local review)" if args.allow_placeholders else ""
    print(f"Validated {len(existing)} HTML pages, internal links, CSP, assets, and release gates{qualifier}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
