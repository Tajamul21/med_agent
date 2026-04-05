import os
import json
import shutil
from pathlib import Path

# ========= CONFIG =========
ROOT_DIR = r"T:\KAUST\med_agent\Combined"
OUTPUT_DIR = r"T:\KAUST\med_agent\MCTA"
IMAGE_DIR_NAME = "image"
OUTPUT_JSON = "mcta.json"
REPORT_TXT = "merge_report.txt"
# ==========================

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS

def load_json(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, json_path: Path):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def update_paths_in_obj(obj, path_map):
    if isinstance(obj, dict):
        return {k: update_paths_in_obj(v, path_map) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [update_paths_in_obj(x, path_map) for x in obj]
    elif isinstance(obj, str):
        normalized = obj.replace("\\", "/")
        for old_path, new_path in path_map.items():
            old_norm = old_path.replace("\\", "/")
            if normalized == old_norm:
                return new_path
            if normalized.endswith("/" + Path(old_norm).name) or normalized == Path(old_norm).name:
                return new_path
        return obj
    else:
        return obj

def collect_sample_jsons(root_dir: Path):
    json_files = []
    for p in root_dir.rglob("*.json"):
        if p.name == OUTPUT_JSON:
            continue
        json_files.append(p)
    return sorted(json_files)

def extract_declared_image_paths(sample):
    declared = []
    if isinstance(sample, dict) and "files" in sample:
        for item in sample.get("files", []):
            if isinstance(item, dict) and item.get("type") == "image":
                rel_path = item.get("path")
                if rel_path:
                    declared.append(rel_path)
    return declared

def find_images_near_json(json_path: Path, sample):
    found_images = []
    missing_declared = []

    declared_paths = extract_declared_image_paths(sample)

    for rel_path in declared_paths:
        candidate = (json_path.parent / rel_path).resolve()
        if candidate.exists() and is_image_file(candidate):
            found_images.append(candidate)
        else:
            missing_declared.append(rel_path)

    if found_images:
        return found_images, missing_declared, declared_paths

    fallback_images = []
    for p in json_path.parent.iterdir():
        if p.is_file() and is_image_file(p):
            fallback_images.append(p)

    return sorted(fallback_images), missing_declared, declared_paths

def write_report(report_path: Path, invalid_jsons, missing_images, no_images, merged_info):
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=== MERGE REPORT ===\n\n")

        f.write(f"Invalid JSON files: {len(invalid_jsons)}\n")
        for item in invalid_jsons:
            f.write(f"- FILE: {item['file']}\n")
            f.write(f"  FOLDER: {item['folder']}\n")
            f.write(f"  ERROR: {item['error']}\n\n")

        f.write(f"JSONs with missing declared image paths: {len(missing_images)}\n")
        for item in missing_images:
            f.write(f"- FILE: {item['file']}\n")
            f.write(f"  FOLDER: {item['folder']}\n")
            f.write(f"  DECLARED: {item['declared']}\n")
            f.write(f"  MISSING: {item['missing']}\n")
            f.write(f"  FOUND_USED: {item['used']}\n\n")

        f.write(f"JSONs with no images found at all: {len(no_images)}\n")
        for item in no_images:
            f.write(f"- FILE: {item['file']}\n")
            f.write(f"  FOLDER: {item['folder']}\n")
            f.write(f"  DECLARED: {item['declared']}\n\n")

        f.write(f"Merged samples: {len(merged_info)}\n")
        for item in merged_info:
            f.write(f"- KEY: {item['key']}\n")
            f.write(f"  FILE: {item['file']}\n")
            f.write(f"  FOLDER: {item['folder']}\n")
            f.write(f"  IMAGES_USED: {item['images_used']}\n\n")

def main():
    root_dir = Path(ROOT_DIR).resolve()
    output_dir = Path(OUTPUT_DIR).resolve()
    image_out_dir = output_dir / IMAGE_DIR_NAME
    report_path = output_dir / REPORT_TXT

    output_dir.mkdir(parents=True, exist_ok=True)
    image_out_dir.mkdir(parents=True, exist_ok=True)

    merged = {}
    image_counter = 1
    sample_counter = 0

    invalid_jsons = []
    missing_images = []
    no_images = []
    merged_info = []

    json_files = collect_sample_jsons(root_dir)

    if not json_files:
        print("No JSON files found.")
        return

    print(f"Found {len(json_files)} JSON files.\n")

    for json_file in json_files:
        try:
            data = load_json(json_file)
        except Exception as e:
            invalid_jsons.append({
                "file": str(json_file),
                "folder": str(json_file.parent),
                "error": str(e)
            })
            print(f"[INVALID JSON] {json_file}")
            print(f"  Folder: {json_file.parent}")
            print(f"  Error : {e}\n")
            continue

        if isinstance(data, dict) and len(data) == 1 and isinstance(next(iter(data.values())), dict):
            sample = next(iter(data.values()))
        else:
            sample = data

        images, missing_declared, declared_paths = find_images_near_json(json_file, sample)

        if missing_declared:
            missing_images.append({
                "file": str(json_file),
                "folder": str(json_file.parent),
                "declared": declared_paths,
                "missing": missing_declared,
                "used": [str(x) for x in images]
            })
            print(f"[MISSING DECLARED IMAGES] {json_file}")
            print(f"  Folder   : {json_file.parent}")
            print(f"  Declared : {declared_paths}")
            print(f"  Missing  : {missing_declared}")
            print(f"  Used     : {[str(x) for x in images]}\n")

        if not images:
            no_images.append({
                "file": str(json_file),
                "folder": str(json_file.parent),
                "declared": declared_paths
            })
            print(f"[NO IMAGES FOUND] {json_file}")
            print(f"  Folder   : {json_file.parent}")
            print(f"  Declared : {declared_paths}\n")
            continue

        path_map = {}
        new_files = []

        for img_path in images:
            new_name = f"image_{image_counter}{img_path.suffix.lower()}"
            new_rel_path = f"{IMAGE_DIR_NAME}/{new_name}"
            dst = image_out_dir / new_name

            shutil.copy2(img_path, dst)

            old_rel_1 = img_path.name
            old_abs = str(img_path).replace("\\", "/")
            path_map[old_rel_1] = new_rel_path
            path_map[old_abs] = new_rel_path

            try:
                old_rel_2 = str(img_path.relative_to(json_file.parent)).replace("\\", "/")
                path_map[old_rel_2] = new_rel_path
            except ValueError:
                pass

            new_files.append({
                "type": "image",
                "path": new_rel_path,
                "url": None
            })

            image_counter += 1

        if isinstance(sample, dict):
            sample = update_paths_in_obj(sample, path_map)
            sample["files"] = new_files

        merged[str(sample_counter)] = sample

        merged_info.append({
            "key": str(sample_counter),
            "file": str(json_file),
            "folder": str(json_file.parent),
            "images_used": [str(x) for x in images]
        })

        sample_counter += 1

    save_json(merged, output_dir / OUTPUT_JSON)
    write_report(report_path, invalid_jsons, missing_images, no_images, merged_info)

    print("\n=== DONE ===")
    print(f"Samples merged : {sample_counter}")
    print(f"Images copied  : {image_counter - 1}")
    print(f"Invalid JSONs  : {len(invalid_jsons)}")
    print(f"Missing images : {len(missing_images)}")
    print(f"No images      : {len(no_images)}")
    print(f"Output JSON    : {output_dir / OUTPUT_JSON}")
    print(f"Output images  : {image_out_dir}")
    print(f"Report file    : {report_path}")

if __name__ == "__main__":
    main()