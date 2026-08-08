#!/usr/bin/env python3
"""MARSEL V21.7 catalog quality gate.

Read-only validator for docs/MARSEL_MASTER_CATALOG_V21.md.
No RO App/API write operations are performed.

The validator is aligned with the current V21 catalog structure. It checks
structural integrity and obvious data-quality defects without treating
legitimate repeated service names across different sections as errors.
"""
from __future__ import annotations

import re
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "docs" / "MARSEL_MASTER_CATALOG_V21.md"

REQUIRED_HEADINGS = [
    "## 1. Типы изделий",
    "## 2. Атрибуты изделия клиента",
    "## 3. Правила классификации складских позиций",
    "## 4. Иерархия категорий и групп",
    "## 5. Правило именования позиции",
    "## 6. Обязательные поля складской карточки",
    "## 7. Складская архитектура MARSEL",
    "## 8. Правила движения",
    "## 9. Ювелирный ремонт",
    "## 10. Камни и закрепка",
    "## 11. Обработка поверхности",
    "## 12. Изготовление и индивидуальные заказы",
    "## 13. Металл клиента",
    "## 14. Часовые услуги",
    "## 15. Результаты диагностики",
    "## 16. Контроль качества перед выдачей",
    "## 17. Себестоимость",
    "## 18. Источник истины и защита от дублей",
    "## 19. Соответствие возможностям RO App",
    "## 20. Что нельзя делать автоматически",
    "## 21. Источники",
]


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if not CATALOG.exists():
        print("ERROR|catalog_missing|docs/MARSEL_MASTER_CATALOG_V21.md")
        return 2

    text = CATALOG.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Validate exact top-level section structure and numbering.
    headings = [line.strip() for line in lines if re.match(r"^##\s+\d+\.\s+", line)]
    for heading in REQUIRED_HEADINGS:
        if heading not in headings:
            errors.append(f"missing_heading|{heading}")

    if len(headings) != len(REQUIRED_HEADINGS):
        errors.append(
            f"top_level_heading_count_mismatch|expected={len(REQUIRED_HEADINGS)}|actual={len(headings)}"
        )

    expected_numbers = list(range(1, len(REQUIRED_HEADINGS) + 1))
    actual_numbers = [int(re.match(r"^##\s+(\d+)\.", heading).group(1)) for heading in headings]
    if actual_numbers != expected_numbers:
        errors.append(f"top_level_heading_numbering|expected={expected_numbers}|actual={actual_numbers}")

    # Detect duplicate top-level headings, which are structural defects.
    heading_counts: dict[str, int] = {}
    for heading in headings:
        heading_counts[heading] = heading_counts.get(heading, 0) + 1
    for heading, count in sorted(heading_counts.items()):
        if count > 1:
            errors.append(f"duplicate_heading|count={count}|{heading}")

    # Parse bullet items together with their current top-level section.
    items: list[tuple[int, str, str]] = []
    current_section = "__preamble__"
    for number, line in enumerate(lines, 1):
        top_heading = re.match(r"^##\s+\d+\.\s+(.+)$", line.strip())
        if top_heading:
            current_section = line.strip()
            continue
        if re.match(r"^\s*-\s+", line):
            item = re.sub(r"^\s*-\s+", "", line).strip()
            if not item:
                errors.append(f"empty_item|line={number}")
            else:
                items.append((number, current_section, item))

    # Duplicate service/catalog terms are only relevant within the same
    # top-level section. Repetition across sections is intentional and valid.
    norm = lambda value: re.sub(r"[^а-яa-z0-9]+", " ", value.lower()).strip()
    seen: dict[tuple[str, str], list[int]] = {}
    for number, section, item in items:
        key = (section, norm(item))
        if key[1]:
            seen.setdefault(key, []).append(number)
    for (section, key), numbers in sorted(seen.items()):
        if len(numbers) > 1:
            warnings.append(
                f"duplicate_item_within_section|lines={','.join(map(str, numbers))}|section={section}|{key}"
            )

    # Obvious unfinished/truncated markers. Markdown URLs are excluded.
    for number, line in enumerate(lines, 1):
        plain = re.sub(r"https?://\S+", "", line)
        if "…" in plain:
            errors.append(f"unfinished_text|line={number}|{line.strip()}")

    # Keep financial/technical values factual: flag numeric price values for
    # human verification rather than inventing or silently accepting them.
    for number, line in enumerate(lines, 1):
        if re.search(r"(?:₽|руб\.?|RUB)\s*\d|\d\s*(?:₽|руб\.?|RUB)", line, re.I):
            warnings.append(f"unverified_price_value|line={number}")

    # Basic punctuation/whitespace defects, excluding Markdown URLs/code spans.
    for number, line in enumerate(lines, 1):
        plain = re.sub(r"`[^`]*`|https?://\S+", "", line)
        if re.search(r"\s+[,:;!?]", plain):
            errors.append(f"space_before_punctuation|line={number}")
        if re.search(r" {2,}$", plain) and not line.endswith("  "):
            errors.append(f"trailing_spaces|line={number}")

    print(f"CATALOG={CATALOG.relative_to(CATALOG.parents[1])}")
    print(f"HEADINGS={len(headings)} ITEMS={len(items)}")
    print(f"ERRORS={len(errors)} WARNINGS={len(warnings)}")
    for error in errors:
        print("ERROR|" + error)
    for warning in warnings:
        print("WARNING|" + warning)
    print("RO_APP_DATA_MUTATED=False")
    print("WRITE_REQUESTS_MADE=0")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
