#!/usr/bin/env python3
"""Extract and validate quizzes from born-digital, multi-column PDFs."""

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


QUESTION_RE = re.compile(
    r"^Q(?:uestion)?\s*(\d{1,4})\s*[.)]\s*(.*)$", re.IGNORECASE
)
BARE_QUESTION_RE = re.compile(r"^(\d{1,4})\s*[.)]\s*(.*)$")
OPTION_RE = re.compile(
    r"^(?:\(([a-h])\)|([a-h])[.)])\s*(.*)$", re.IGNORECASE
)
FOOTER_RE = re.compile(
    r"^(?:\d+\s+)?www\.[^\s]+.*$|^Adda247 App$|^\|$", re.IGNORECASE
)
STRUCTURE_RE = re.compile(
    r"^(?:"
    r"Q(?:uestion)?\s*\d{1,4}\s*[.)]|"
    r"(?:\([a-h]\)|[a-h][.)])|"
    r"Directions?\b|Instructions?\b|"
    r"Assumptions?\s*:|Courses? of Actions?\s*:|"
    r"Input\s*:|Step\s+[IVX]+\s*:|"
    r"Note\s+(?:\d+|[IVX]+)\s*:|[IVX]+\."
    r")",
    re.IGNORECASE,
)


def normalize_line(line):
    line = line.replace("\u00a0", " ").replace("\u200b", "")
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"\s+([,.;:?!])", r"\1", line)
    split_q = re.match(
        r"^Q(?:uestion)?\s*((?:\d\s*)+)([.)])\s*(.*)$",
        line,
        re.IGNORECASE,
    )
    if split_q:
        digits = re.sub(r"\s+", "", split_q.group(1))
        line = f"Q{digits}{split_q.group(2)} {split_q.group(3)}".strip()
    return line


def is_noise(line):
    return not line or FOOTER_RE.match(line) or line.isdigit()


def stream_pages(reader, max_pages=None):
    pages = []
    for page in reader.pages[:max_pages]:
        lines = []
        for raw in (page.extract_text() or "").splitlines():
            line = normalize_line(raw)
            if not line:
                if lines and lines[-1] is not None:
                    lines.append(None)
            elif not is_noise(line):
                lines.append(line)
        pages.append(lines)
    return pages


def positioned_fragments(page):
    fragments = []

    def visitor(text, _cm, tm, _font, font_size):
        text = normalize_line(text)
        x, y = float(tm[4]), float(tm[5])
        if not text or (x == 0 and y == 0):
            return
        width = max(float(font_size) * 0.28 * len(text), float(font_size))
        fragments.append({
            "text": text,
            "x0": x,
            "x1": x + width,
            "y": y,
            "size": float(font_size),
        })

    page.extract_text(visitor_text=visitor)
    return fragments


def group_visual_lines(fragments):
    rows = []
    for fragment in sorted(fragments, key=lambda item: -item["y"]):
        tolerance = max(2.0, fragment["size"] * 0.35)
        row = next(
            (candidate for candidate in rows
             if abs(candidate["y"] - fragment["y"]) <= tolerance),
            None,
        )
        if row is None:
            row = {"y": fragment["y"], "items": []}
            rows.append(row)
        row["items"].append(fragment)

    visual_lines = []
    for row in rows:
        items = sorted(row["items"], key=lambda item: item["x0"])
        text = " ".join(item["text"] for item in items)
        visual_lines.append({
            "text": normalize_line(text),
            "x0": min(item["x0"] for item in items),
            "x1": max(item["x1"] for item in items),
            "y": row["y"],
        })
    return visual_lines


def infer_column_starts(items, page_width):
    bins = Counter()
    for item in items:
        if item["x0"] < page_width * 0.04:
            continue
        bucket = round(item["x0"] / 12) * 12
        bins[bucket] += 1

    min_count = max(5, math.ceil(max(bins.values(), default=0) * 0.20))
    candidates = [
        x for x, count in bins.most_common(12)
        if count >= min_count and x < page_width * 0.92
    ]
    starts = []
    for x in sorted(candidates):
        if not starts or x - starts[-1] >= page_width * 0.18:
            starts.append(x)
        elif bins[x] > bins[starts[-1]]:
            starts[-1] = x
    return starts[:4] or [0]


def coordinate_page(page):
    width = float(page.mediabox.width)
    fragments = positioned_fragments(page)
    if not fragments:
        return []

    starts = infer_column_starts(fragments, width)
    if len(starts) == 1:
        lines = [
            line for line in group_visual_lines(fragments)
            if not is_noise(line["text"])
        ]
        return [line["text"] for line in sorted(lines, key=lambda x: -x["y"])]

    boundaries = [start - width * 0.025 for start in starts[1:]]
    column_fragments = [[] for _ in starts]
    for fragment in fragments:
        column = sum(fragment["x0"] >= boundary for boundary in boundaries)
        column_fragments[column].append(fragment)

    ordered = []
    for fragments_in_column in column_fragments:
        lines = [
            line for line in group_visual_lines(fragments_in_column)
            if not is_noise(line["text"])
        ]
        ordered.extend(sorted(lines, key=lambda item: -item["y"]))
    return [line["text"] for line in ordered]


def coordinate_pages(reader, max_pages=None):
    return [coordinate_page(page) for page in reader.pages[:max_pages]]


def logical_blocks(lines, allow_bare=False):
    blocks = []
    force_new = True
    for line in lines:
        if line is None:
            force_new = True
            continue
        starts_block = bool(STRUCTURE_RE.match(line)) or (
            allow_bare and bool(BARE_QUESTION_RE.match(line))
        )
        if not blocks or starts_block or force_new:
            blocks.append(line)
        else:
            blocks[-1] = f"{blocks[-1]} {line}"
        force_new = False
    return blocks


def question_match(block, allow_bare=False):
    match = QUESTION_RE.match(block)
    if not match and allow_bare:
        match = BARE_QUESTION_RE.match(block)
    return match


def question_number(block, allow_bare=False):
    match = question_match(block, allow_bare)
    return int(match.group(1)) if match else None


def longest_sequence(numbers):
    if not numbers:
        return []
    best = current = [numbers[0]]
    for number in numbers[1:]:
        if number == current[-1] + 1:
            current.append(number)
        elif number != current[-1]:
            current = [number]
        if len(current) > len(best):
            best = current
    return best


def build_questions(
    page_blocks, first_question=None, last_question=None, allow_bare=False
):
    seen_numbers = [
        question_number(block, allow_bare)
        for blocks in page_blocks for block in blocks
        if question_number(block, allow_bare) is not None
    ]
    sequence = longest_sequence(seen_numbers)
    if not sequence:
        return [], None, None

    first = first_question if first_question is not None else sequence[0]
    last = last_question if last_question is not None else sequence[-1]
    questions = []
    current = None
    expected = first

    for page_idx, blocks in enumerate(page_blocks):
        for block in blocks:
            match = question_match(block, allow_bare)
            if match and int(match.group(1)) == expected:
                if current:
                    questions.append(current)
                current = {
                    "number": expected,
                    "page": page_idx + 1,
                    "question": match.group(2).strip(),
                    "options": {},
                }
                expected += 1
                continue
            if not current:
                continue

            option = OPTION_RE.match(block)
            if option:
                key = (option.group(1) or option.group(2)).lower()
                current["options"][key] = option.group(3).strip()
            elif current["options"] and STRUCTURE_RE.match(block):
                continue
            elif current["options"]:
                key = next(reversed(current["options"]))
                current["options"][key] = f"{current['options'][key]} {block}".strip()
            else:
                current["question"] = f"{current['question']} {block}".strip()

    if current:
        questions.append(current)
    return [q for q in questions if first <= q["number"] <= last], first, last


def contiguous_option_count(question):
    count = 0
    for letter in "abcdefgh":
        if letter not in question["options"]:
            break
        count += 1
    return count


def infer_option_counts(questions):
    complete_counts = {
        q["number"]: contiguous_option_count(q)
        for q in questions
        if len(q["options"]) == contiguous_option_count(q)
        and contiguous_option_count(q) >= 2
    }
    distribution = Counter(complete_counts.values())
    global_count = (
        distribution.most_common(1)[0][0]
        if distribution
        else 0
    )
    inferred = {}
    for question in questions:
        nearby = [
            count for number, count in complete_counts.items()
            if abs(number - question["number"]) <= 5
        ]
        inferred[question["number"]] = (
            Counter(nearby).most_common(1)[0][0]
            if nearby
            else global_count
        )
    return inferred, dict(sorted(distribution.items()))


def validate_questions(questions, first, last, expected_options):
    numbers = [q["number"] for q in questions]
    missing = [number for number in range(first, last + 1) if number not in numbers]
    auto_options = expected_options in (None, "auto", 0)
    inferred_counts, distribution = infer_option_counts(questions)
    incomplete = {
        q["number"]: [
            letter for letter in "abcdefgh"[:(
                inferred_counts.get(q["number"], 0)
                if auto_options
                else int(expected_options)
            )]
            if letter not in q["options"]
        ]
        for q in questions
        if any(
            letter not in q["options"]
            for letter in "abcdefgh"[:(
                inferred_counts.get(q["number"], 0)
                if auto_options
                else int(expected_options)
            )]
        )
    }
    duplicates = sorted(number for number, count in Counter(numbers).items() if count > 1)
    return {
        "first_question": first,
        "last_question": last,
        "expected_questions": last - first + 1,
        "extracted_questions": len(questions),
        "missing_questions": missing,
        "duplicate_questions": duplicates,
        "incomplete_options": incomplete,
        "option_mode": "auto" if auto_options else "manual",
        "detected_option_distribution": distribution if auto_options else None,
        "valid": not missing and not duplicates and not incomplete,
    }


def candidate_score(report):
    return (
        report["extracted_questions"] * 20
        - len(report["missing_questions"]) * 50
        - len(report["duplicate_questions"]) * 30
        - len(report["incomplete_options"]) * 10
    )


def analyze_candidate(
    name, pages, first, last, expected_options, allow_bare=False
):
    blocks = [logical_blocks(page, allow_bare) for page in pages]
    questions, detected_first, detected_last = build_questions(
        blocks, first, last, allow_bare
    )
    if not questions:
        return {
            "name": name,
            "pages": blocks,
            "questions": [],
            "report": {"valid": False, "error": "No sequential quiz detected"},
            "score": -math.inf,
        }
    report = validate_questions(
        questions, detected_first, detected_last, expected_options
    )
    return {
        "name": name,
        "pages": blocks,
        "questions": questions,
        "report": report,
        "score": candidate_score(report),
    }


def render_markdown(page_blocks, valid_numbers, allow_bare=False):
    output = []
    for page_idx, blocks in enumerate(page_blocks):
        if page_idx:
            output.extend(["", f"<!-- Page {page_idx + 1} -->", ""])
        for block in blocks:
            number = question_number(block, allow_bare)
            if number in valid_numbers:
                match = question_match(block, allow_bare)
                output.extend(["", f"## Q{number}. {match.group(2).strip()}", ""])
            elif block.lower().startswith(("direction", "instruction")):
                output.extend(["", f"### {block}", ""])
            else:
                output.extend([block, ""])
    return "\n".join(output).strip() + "\n"


def build_content_lists(page_blocks, valid_numbers, allow_bare=False):
    flat, v2 = [], []
    for page_idx, blocks in enumerate(page_blocks):
        page_items = []
        for block in blocks:
            number = question_number(block, allow_bare)
            is_heading = number in valid_numbers
            is_directions = block.lower().startswith(("direction", "instruction"))
            item_type = "title" if is_heading or is_directions else "paragraph"
            key = "title_content" if item_type == "title" else "paragraph_content"
            content = {key: [{"type": "text", "content": block}]}
            if item_type == "title":
                content["level"] = 2 if is_heading else 3
            page_items.append({
                "type": item_type,
                "content": content,
                "bbox": [0, 0, 0, 0],
            })
            flat.append({
                "type": "text",
                "text": block,
                "page_idx": page_idx,
                "source": "pdf_native_text",
            })
        v2.append(page_items)
    return flat, v2


def compare_mineru(content_v2_path, first, last):
    if not content_v2_path:
        return None
    data = json.loads(Path(content_v2_path).read_text(encoding="utf-8"))
    text = json.dumps(data, ensure_ascii=False)
    found = {int(value) for value in re.findall(
        r"\bQ\s*(\d{1,4})\s*[.)]", text, re.IGNORECASE
    )}
    return {
        "questions_found": len([n for n in found if first <= n <= last]),
        "missing_questions": [
            n for n in range(first, last + 1) if n not in found
        ],
    }


def repair_quiz_pdf(
    pdf_path,
    output_prefix,
    expected_options="auto",
    mineru_content_v2=None,
    first_question=None,
    last_question=None,
    allow_bare_question_numbers=False,
    max_pages=None,
):
    pdf_path = Path(pdf_path).resolve()
    prefix = Path(output_prefix).resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(pdf_path))
    candidates = [
        analyze_candidate(
            "native_stream",
            stream_pages(reader, max_pages),
            first_question,
            last_question,
            expected_options,
            allow_bare_question_numbers,
        ),
        analyze_candidate(
            "coordinate_columns",
            coordinate_pages(reader, max_pages),
            first_question,
            last_question,
            expected_options,
            allow_bare_question_numbers,
        ),
    ]
    best = max(candidates, key=lambda candidate: candidate["score"])
    report = dict(best["report"])
    if "first_question" not in report:
        report.update({
            "selected_strategy": best["name"],
            "candidate_scores": {
                candidate["name"]: candidate["score"] for candidate in candidates
            },
            "mineru_audit": None,
        })
        return report

    report["selected_strategy"] = best["name"]
    report["candidate_scores"] = {
        candidate["name"]: candidate["score"] for candidate in candidates
    }
    report["mineru_audit"] = compare_mineru(
        mineru_content_v2,
        report["first_question"],
        report["last_question"],
    )

    valid_numbers = {q["number"] for q in best["questions"]}
    flat, v2 = build_content_lists(
        best["pages"], valid_numbers, allow_bare_question_numbers
    )
    prefix.with_suffix(".md").write_text(
        render_markdown(
            best["pages"], valid_numbers, allow_bare_question_numbers
        ),
        encoding="utf-8",
    )
    prefix.with_suffix(".json").write_text(
        json.dumps(best["questions"], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    prefix.with_name(f"{prefix.name}_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    prefix.with_name(f"{prefix.name}_content_list.json").write_text(
        json.dumps(flat, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    prefix.with_name(f"{prefix.name}_content_list_v2.json").write_text(
        json.dumps(v2, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="born-digital quiz PDF")
    parser.add_argument("-o", "--output-prefix")
    parser.add_argument("--first-question", type=int)
    parser.add_argument("--last-question", "--max-question", type=int)
    parser.add_argument(
        "--expected-options",
        default="auto",
        choices=["auto", "2", "3", "4", "5", "6", "7", "8"],
        help="auto infers option count from nearby questions (default)",
    )
    parser.add_argument(
        "--allow-bare-question-numbers",
        action="store_true",
        help="treat lines like '1.' as questions; explicit Q/Question is safer",
    )
    parser.add_argument("--mineru-content-v2", help="optional MinerU output to audit")
    parser.add_argument("--max-pages", type=int)
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.is_file():
        sys.exit(f"PDF not found: {pdf_path}")
    prefix = (
        Path(args.output_prefix).resolve()
        if args.output_prefix
        else pdf_path.with_name(f"{pdf_path.stem}_quiz_repaired")
    )
    report = repair_quiz_pdf(
        pdf_path=pdf_path,
        output_prefix=prefix,
        expected_options=args.expected_options,
        mineru_content_v2=args.mineru_content_v2,
        first_question=args.first_question,
        last_question=args.last_question,
        allow_bare_question_numbers=args.allow_bare_question_numbers,
        max_pages=args.max_pages,
    )

    print(json.dumps(report, indent=2))
    if not report["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
