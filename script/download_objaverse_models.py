#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import multiprocessing
import shutil
from pathlib import Path
from typing import Any

import yaml


DEFAULT_ALIASES = {
    "dog": ["dog", "puppy"],
    "cat": ["cat", "kitten"],
    "person": ["person", "human", "man", "woman"],
    "ball": ["ball", "sports ball", "soccer ball", "basketball"],
    "bowl": ["bowl", "dish"],
    "bed": ["bed"],
    "chair": ["chair", "seat"],
    "potted_plant": ["potted plant", "plant pot", "houseplant", "plant"],
}

DEFAULT_LVIS_CATEGORIES = {
    "dog": ["dog"],
    "cat": ["cat"],
    "person": ["person"],
    "ball": [
        "ball",
        "baseball",
        "basketball",
        "soccer ball",
        "tennis ball",
        "volleyball",
    ],
    "bowl": ["bowl"],
    "bed": ["bed"],
    "chair": ["chair"],
    "potted_plant": ["potted plant", "flowerpot"],
}


def load_object_names(config_path: Path) -> list[str]:
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    objects = config.get("objects", {})
    if not isinstance(objects, dict):
        raise ValueError(f"Invalid object config: {config_path}")

    return list(objects.keys())


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ")


def annotation_terms(annotation: dict) -> tuple[str, list[str]]:
    name = normalize_text(annotation.get("name"))
    terms = [name]

    for tag in annotation.get("tags") or []:
        if isinstance(tag, dict):
            terms.append(normalize_text(tag.get("name")))
            terms.append(normalize_text(tag.get("slug")))
        else:
            terms.append(normalize_text(tag))

    for category in annotation.get("categories") or []:
        if isinstance(category, dict):
            terms.append(normalize_text(category.get("name")))
            terms.append(normalize_text(category.get("slug")))
        else:
            terms.append(normalize_text(category))

    return name, [term for term in terms if term]


def archive_has_glb(annotation: dict) -> bool:
    archives = annotation.get("archives") or {}
    return bool(archives.get("glb"))


def score_annotation(annotation: dict, aliases: list[str]) -> int:
    name, terms = annotation_terms(annotation)
    score = 0

    for alias in aliases:
        alias = normalize_text(alias)
        if not alias:
            continue

        if alias == name:
            score += 100
        elif alias in name:
            score += 60

        for term in terms:
            if alias == term:
                score += 25
            elif alias in term:
                score += 10

    return score


def find_lvis_categories(
    lvis_annotations: dict[str, list[str]],
    object_name: str,
) -> list[str]:
    category_aliases = DEFAULT_LVIS_CATEGORIES.get(
        object_name,
        [object_name, object_name.replace("_", " ")],
    )
    normalized_aliases = {
        normalize_text(alias)
        for alias in category_aliases
    }

    matches = []
    for category in lvis_annotations:
        normalized_category = normalize_text(category)
        if normalized_category in normalized_aliases:
            matches.append(category)

    return sorted(matches)


def collect_lvis_uids(
    lvis_annotations: dict[str, list[str]],
    object_name: str,
    max_uids: int,
) -> tuple[list[str], list[str]]:
    categories = find_lvis_categories(lvis_annotations, object_name)
    collected_uids = []
    seen_uids = set()

    for category in categories:
        for uid in lvis_annotations[category]:
            if uid in seen_uids:
                continue

            seen_uids.add(uid)
            collected_uids.append(uid)

            if len(collected_uids) >= max_uids:
                return collected_uids, categories

    return collected_uids, categories


def select_candidates(
    annotations: dict[str, dict],
    object_name: str,
    max_count: int,
    license_filter: str,
    min_score: int,
) -> list[tuple[str, dict, int]]:
    aliases = DEFAULT_ALIASES.get(
        object_name,
        [object_name, object_name.replace("_", " ")],
    )
    candidates = []

    for uid, annotation in annotations.items():
        if not annotation.get("isDownloadable", False):
            continue

        if not archive_has_glb(annotation):
            continue

        if license_filter != "any" and annotation.get("license") != license_filter:
            continue

        score = score_annotation(annotation, aliases)
        if score < min_score:
            continue

        candidates.append((uid, annotation, score))

    candidates.sort(
        key=lambda item: (
            item[2],
            int(item[1].get("likeCount") or 0),
            int(item[1].get("viewCount") or 0),
        ),
        reverse=True,
    )
    return candidates[:max_count]


def select_candidates_from_lvis(
    objaverse_module,
    lvis_annotations: dict[str, list[str]],
    object_name: str,
    max_count: int,
    license_filter: str,
    min_score: int,
    uid_candidates: int,
) -> tuple[list[tuple[str, dict, int]], list[str], int]:
    uid_pool, categories = collect_lvis_uids(
        lvis_annotations=lvis_annotations,
        object_name=object_name,
        max_uids=uid_candidates,
    )

    if not uid_pool:
        return [], categories, 0

    annotations = objaverse_module.load_annotations(uid_pool)
    candidates = select_candidates(
        annotations=annotations,
        object_name=object_name,
        max_count=max_count,
        license_filter=license_filter,
        min_score=min_score,
    )

    return candidates, categories, len(uid_pool)


def copy_downloaded_models(
    downloaded_paths: dict[str, str],
    selected: dict[str, list[tuple[str, dict, int]]],
    output_dir: Path,
) -> list[dict]:
    manifest = []

    for object_name, candidates in selected.items():
        object_dir = output_dir / object_name
        object_dir.mkdir(parents=True, exist_ok=True)

        for uid, annotation, score in candidates:
            source_path = Path(downloaded_paths[uid])
            target_path = object_dir / f"{uid}.glb"

            if not target_path.exists():
                shutil.copy2(source_path, target_path)

            manifest.append(
                {
                    "object": object_name,
                    "uid": uid,
                    "score": score,
                    "name": annotation.get("name"),
                    "license": annotation.get("license"),
                    "viewerUrl": annotation.get("viewerUrl"),
                    "source_path": str(source_path),
                    "output_path": str(target_path),
                }
            )

    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download Objaverse 1.0 GLB models matching config/object.yaml objects."
        )
    )
    parser.add_argument("--config", default="config/object.yaml")
    parser.add_argument("--output-dir", default="models/objaverse")
    parser.add_argument(
        "--objects",
        nargs="+",
        help="Object names to download. Defaults to every object in config.",
    )
    parser.add_argument("--max-per-object", type=int, default=1)
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help=(
            "Optional metadata text-match score filter after LVIS category "
            "selection. Defaults to 0 because LVIS already narrows the class."
        ),
    )
    parser.add_argument(
        "--uid-candidates-per-object",
        type=int,
        default=100,
        help=(
            "Maximum LVIS UIDs per object to inspect with load_annotations(). "
            "Keeps memory bounded."
        ),
    )
    parser.add_argument(
        "--license",
        default="by",
        help="License filter. Use 'any' to disable filtering.",
    )
    parser.add_argument(
        "--download-processes",
        type=int,
        default=max(1, min(multiprocessing.cpu_count(), 4)),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Select candidates and write manifest without downloading GLBs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    object_names = args.objects or load_object_names(config_path)

    try:
        import objaverse
    except ImportError as exc:
        raise RuntimeError(
            "objaverse is required. Install it with: pip install objaverse"
        ) from exc

    print("[OBJAVERSE] loading LVIS annotations")
    lvis_annotations = objaverse.load_lvis_annotations()

    selected: dict[str, list[tuple[str, dict, int]]] = {}
    for object_name in object_names:
        candidates, categories, uid_pool_size = select_candidates_from_lvis(
            objaverse_module=objaverse,
            lvis_annotations=lvis_annotations,
            object_name=object_name,
            max_count=max(1, args.max_per_object),
            license_filter=args.license,
            min_score=args.min_score,
            uid_candidates=max(1, args.uid_candidates_per_object),
        )
        selected[object_name] = candidates
        print(
            f"[OBJAVERSE] {object_name}: "
            f"LVIS categories={categories or 'none'} "
            f"inspected_uids={uid_pool_size} "
            f"selected={len(candidates)}"
        )
        for uid, annotation, score in candidates:
            print(
                "  "
                f"score={score} uid={uid} "
                f"license={annotation.get('license')} "
                f"name={annotation.get('name')}"
            )

    selected_uids = [
        uid
        for candidates in selected.values()
        for uid, _, _ in candidates
    ]
    if not selected_uids:
        print("[OBJAVERSE] no matching candidates found")

    if args.dry_run:
        manifest = [
            {
                "object": object_name,
                "uid": uid,
                "score": score,
                "name": annotation.get("name"),
                "license": annotation.get("license"),
                "viewerUrl": annotation.get("viewerUrl"),
                "source_path": None,
                "output_path": None,
            }
            for object_name, candidates in selected.items()
            for uid, annotation, score in candidates
        ]
    elif not selected_uids:
        manifest = []
    else:
        print(f"[OBJAVERSE] downloading {len(selected_uids)} GLB model(s)")
        downloaded_paths = objaverse.load_objects(
            uids=selected_uids,
            download_processes=max(1, args.download_processes),
        )
        manifest = copy_downloaded_models(downloaded_paths, selected, output_dir)

    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    print(f"[OBJAVERSE] wrote manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
