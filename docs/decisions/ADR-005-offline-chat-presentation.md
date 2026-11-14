# ADR-005: Dependency-free offline chat presentation

Date: 2026-11-14
Status: Accepted

## Context
Plain alias names and bare message boxes were difficult to read. Preserve the existing security boundary, Python 3.9 stdlib requirement and v1 archives.

## Decision
Use an independently authored small common alias dictionary, Unicode glyphs from OS fonts, inline responsive CSS, deterministic initials/color avatars and native HTML anchors/details. Group synonymous aliases by Unicode; chip counts mean distinct exact usernames, not reaction records. Preserve all original records, aliases and exact ISO times in accessible details. Direct replies have their own localized count; nested replies expand independently. Keep original exact count markers and manifest schema. Attachment bytes remain download-only, never inline HTML/SVG.

## Alternatives considered
Preflight checked the existing Python emoji package on PyPI (https://pypi.org/project/emoji/ and its JSON metadata). A full third-party dataset/package adds dependency and licensing/update obligations unnecessary for this bounded common subset. No package, dataset, image, font, CSS or code was copied; no borrowed-asset license applies. An upstream chat frontend would add JavaScript/network complexity contrary to the offline inert design.

## Consequences
Unknown/custom aliases retain escaped :name: text; no external custom asset lookup. Glyph appearance varies with installed fonts. This is not full Mattermost UI fidelity or safe attachment sanitization. Existing raw exports can be reconverted without server access, into a new output filename.
