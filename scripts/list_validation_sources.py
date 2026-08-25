from __future__ import annotations

from uas_thermal.validation.external_sources import SOURCES


def main() -> int:
    for source in SOURCES:
        print(source.source_id)
        print(f"  title: {source.title}")
        print(f"  source: {source.landing_url}")
        print(f"  license: {source.license}")
        print(f"  redistribution: {source.redistribution}")
        if source.checksum:
            print(f"  checksum: {source.checksum_algorithm}:{source.checksum}")
        print("  validates:")
        for purpose in source.purpose:
            print(f"    - {purpose}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
