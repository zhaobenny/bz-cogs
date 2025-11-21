import platform

# Only check AVX support on x86 CPUs and skip macOS
if platform.system() != "Darwin":
    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64", "i386", "x86"):
        from cpuinfo import get_cpu_info

        cpu_info: dict = get_cpu_info()
        flags = [f.lower() for f in cpu_info.get("flags", [])]

        if "avx" not in flags:
            raise ImportError(
                "VectorStore is not supported on this CPU. AVX support is required."
            )

from .vectorstore import VectorStore

__all__ = ["VectorStore"]
