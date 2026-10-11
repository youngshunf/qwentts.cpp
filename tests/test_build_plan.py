"""构建参数和平台拒绝规则的轻量验证，不执行其他平台的构建。"""

import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("build_library", Path(__file__).resolve().parents[1] / "scripts/build/build-library.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class BuildPlanTests(unittest.TestCase):
    def plan(self, target):
        return BUILD.build_plan(target, Path("/ggml"), Path("/build"), 2)

    def test_macos_keeps_cpu_and_metal(self):
        configure, build, test = self.plan("macos-aarch64")
        self.assertIn("-DGGML_METAL=ON", configure)
        self.assertIn("-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16", configure)
        self.assertIn("-DGGML_NATIVE=OFF", configure)
        self.assertIn("-DQWEN_SHARED=ON", configure)
        self.assertIn("test-backend-abi", build)
        self.assertEqual(test[0], "ctest")

    def test_windows_requires_vulkan_and_cuda(self):
        configure, _, _ = self.plan("windows-x86_64")
        for flag in ("-DGGML_VULKAN=ON", "-DGGML_CUDA=ON", "-DGGML_BACKEND_DL=ON", "-DGGML_CPU_ALL_VARIANTS=ON"):
            self.assertIn(flag, configure)

    def test_linux_is_desktop_vulkan(self):
        configure, _, _ = self.plan("linux-x86_64")
        self.assertIn("-DGGML_VULKAN=ON", configure)
        self.assertIn("-DGGML_CUDA=OFF", configure)
        self.assertIn("-DGGML_BACKEND_DL=ON", configure)

    def test_invalid_platform_and_parallelism_are_rejected(self):
        with self.assertRaises(ValueError):
            self.plan("macos-x86_64")
        with self.assertRaises(ValueError):
            BUILD.build_plan("macos-aarch64", Path("/ggml"), Path("/build"), 0)

    def test_source_build_is_rejected_before_dependency_lookup(self):
        with self.assertRaisesRegex(ValueError, "源码树外"):
            BUILD.validate_paths(Path("/ggml"), BUILD.SOURCE / "build")

    def test_receipt_rejects_a_different_source_revision(self):
        current = BUILD.source_state()
        BUILD.verify_source_state(current)
        with self.assertRaisesRegex(ValueError, "源码发生变化"):
            BUILD.verify_source_state(("0" * 40, current[1], current[2]))


if __name__ == "__main__":
    unittest.main()
