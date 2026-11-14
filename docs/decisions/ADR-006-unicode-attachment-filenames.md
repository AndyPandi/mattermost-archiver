# ADR-006: Unicode attachment filenames

Date: 2026-11-14
Status: Accepted

## Context
ASCII replacement obscured Korean attachment names, and unencoded hrefs would misinterpret spaces, percent signs and fragments after Unicode preservation.

## Decision
Preserve Unicode/ordinary spaces, normalize the output basename only to NFC, and use `stem_last8hash.ext` with one underscore. Keep exact original member lookup/hash and full content integrity SHA-256. Use NFC+casefold collision keys and existing 4-digit expansion through 64. Sanitize cross-platform reserved/control names, bound components to 240 UTF-8 bytes/UTF-16 units, and preserve final extensions only when within 32 bytes/units; oversized extensions become stem text rather than a misleading truncated extension. URL-encode hrefs before HTML escaping.

## Alternatives Considered
ASCII-only names lose readability; arbitrary code-point length caps do not protect byte-limited filesystems; truncated extensions can misidentify file types.

## Consequences
Existing raw exports can be reconverted to a new output ZIP without server re-export. Old archives remain unchanged and verifiable. Display names remain escaped originals. Extremely long filenames can lose stem text or their oversized extension.
