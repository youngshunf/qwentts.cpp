#!/usr/bin/env python3
"""三平台原生构建入口；只编库和专项测试，不发布安装包。"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

SOURCE = Path(__file__).resolve().parents[2]
PLATFORMS = {
    "macos-aarch64": ("Darwin", {"arm64", "aarch64"}),
    "windows-x86_64": ("Windows", {"amd64", "x86_64"}),
    "linux-x86_64": ("Linux", {"amd64", "x86_64"}),
}


def build_plan(target, ggml_source, build_dir, jobs):
    """使用上游 CMake/GGML 能力，保留显式可审查的参数。"""
    if target not in PLATFORMS or jobs < 1:
        raise ValueError("平台未知或并行数小于 1")
    macos = target == "macos-aarch64"
    windows = target == "windows-x86_64"
    flags = {
        "CMAKE_BUILD_TYPE": "Release",
        "QWEN_SHARED": "ON",
        "BUILD_SHARED_LIBS": "ON",
        "GGML_SOURCE_DIR": str(ggml_source),
        "GGML_NATIVE": "OFF",
        "GGML_METAL": "ON" if macos else "OFF",
        "GGML_METAL_EMBED_LIBRARY": "ON" if macos else "OFF",
        "GGML_VULKAN": "OFF" if macos else "ON",
        "GGML_CUDA": "ON" if windows else "OFF",
        "GGML_BLAS": "OFF",
        "GGML_BACKEND_DL": "OFF" if macos else "ON",
        "GGML_CPU_ALL_VARIANTS": "OFF" if macos else "ON",
    }
    if macos:
        flags["CMAKE_OSX_ARCHITECTURES"] = "arm64"
        flags["CMAKE_OSX_DEPLOYMENT_TARGET"] = "13.0"
        flags["GGML_CPU_ARM_ARCH"] = "armv8.2-a+dotprod+fp16"
    configure = ["cmake", "-S", str(SOURCE), "-B", str(build_dir)]
    configure.extend(f"-D{key}={value}" for key, value in flags.items())
    build = ["cmake", "--build", str(build_dir), "--config", "Release", "--target",
             "qwen", "test-abi-c", "test-backend-abi", "--parallel", str(jobs)]
    test = ["ctest", "--test-dir", str(build_dir), "-C", "Release", "--output-on-failure"]
    return [configure, build, test]


def git(directory, *args):
    return subprocess.check_output(["git", "-C", str(directory), *args], text=True).strip()


def source_state():
    """防止构建期间切换提交，导致旧二进制被标成新修订。"""
    return (git(SOURCE, "rev-parse", "HEAD"), git(SOURCE, "status", "--porcelain"),
            git(SOURCE, "diff", "--no-ext-diff", "HEAD"))


def verify_source_state(initial_state):
    if source_state() != initial_state:
        raise ValueError("构建期间源码发生变化，本轮不得生成成功回执")


def validate_paths(ggml_source, build_dir):
    if build_dir == SOURCE or SOURCE in build_dir.parents:
        raise ValueError("构建目录必须在源码树外")
    if build_dir == ggml_source or ggml_source in build_dir.parents:
        raise ValueError("构建目录不能写入 GGML 源码树")
    expected = git(SOURCE, "ls-tree", "HEAD", "ggml").split()[2]
    actual = git(ggml_source, "rev-parse", "HEAD")
    if actual != expected or git(ggml_source, "status", "--porcelain"):
        raise ValueError(f"GGML 必须是干净的钉死提交：{expected}")
    return expected


def artifact_manifest(target, build_dir, commands, ggml_revision):
    artifacts = []
    for path in sorted(build_dir.rglob("*")):
        if not path.is_file() or not (path.name.endswith((".dylib", ".dll", ".so")) or ".so." in path.name):
            continue
        if target == "macos-aarch64":
            inspect = ["otool", "-L", str(path)]
        elif target == "windows-x86_64":
            inspect = ["dumpbin", "/dependents", str(path)]
        else:
            inspect = ["readelf", "-d", str(path)]
        links = subprocess.check_output(inspect, text=True)
        with path.open("rb") as content:
            digest = hashlib.file_digest(content, "sha256").hexdigest()
        artifacts.append({"path": str(path.relative_to(build_dir)), "byte_size": path.stat().st_size,
                          "sha256": digest,
                          "dynamic_links": links})
    if not any(Path(item["path"]).name in {"libqwen.dylib", "libqwen.so", "qwen.dll"} for item in artifacts):
        raise ValueError("缺少 qwen 动态库，不能生成成功回执")
    return {"platform": target, "source_revision": git(SOURCE, "rev-parse", "HEAD"),
            "source_dirty": bool(git(SOURCE, "status", "--porcelain")),
            "ggml_revision": ggml_revision, "commands": commands, "artifacts": artifacts,
            "publication_status": "not_published"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=PLATFORMS, required=True)
    parser.add_argument("--ggml-source", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    args.ggml_source = args.ggml_source.resolve()
    args.build_dir = args.build_dir.resolve()
    commands = build_plan(args.platform, args.ggml_source, args.build_dir, args.jobs)
    if args.plan:
        print(json.dumps(commands, ensure_ascii=False, indent=2))
        return
    system, machines = PLATFORMS[args.platform]
    if platform.system() != system or platform.machine().lower() not in machines:
        raise ValueError("必须在目标平台原生构建；跨平台计划不能冒充真机证据")
    revision = validate_paths(args.ggml_source, args.build_dir)
    initial_state = source_state()
    args.build_dir.mkdir(parents=True, exist_ok=True)
    for command in commands:
        subprocess.run(command, check=True)
    verify_source_state(initial_state)
    manifest = artifact_manifest(args.platform, args.build_dir, commands, revision)
    (args.build_dir / "build-receipt.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
