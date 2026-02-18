"""
Resource Checker — monitors system resources using stdlib only.

Checks disk space, memory, CPU usage, vault accessibility,
and API endpoint connectivity. No psutil dependency.
"""

import logging
import os
import shutil
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("health-monitor.resources")


class ResourceChecker:
    """
    System resource monitoring using Python stdlib.

    Reads /proc/ filesystem for memory and CPU on Linux.
    Uses shutil.disk_usage() for disk space.
    Uses urllib for API connectivity checks.
    """

    def __init__(
        self,
        disk_threshold: float = 90.0,
        memory_threshold: float = 90.0,
        cpu_threshold: float = 90.0,
    ) -> None:
        self.disk_threshold = disk_threshold
        self.memory_threshold = memory_threshold
        self.cpu_threshold = cpu_threshold

    # ------------------------------------------------------------------
    # Disk
    # ------------------------------------------------------------------
    def check_disk(self, path: str = "/") -> Dict[str, Any]:
        """
        Check disk usage for the given path.

        Returns:
            {total_gb, used_gb, free_gb, percent_used, ok}
        """
        try:
            usage = shutil.disk_usage(path)
            total_gb = round(usage.total / (1024 ** 3), 2)
            used_gb = round(usage.used / (1024 ** 3), 2)
            free_gb = round(usage.free / (1024 ** 3), 2)
            percent_used = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0

            return {
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "percent_used": percent_used,
                "ok": percent_used < self.disk_threshold,
            }
        except OSError as e:
            logger.error("Disk check failed for %s: %s", path, e)
            return {
                "total_gb": 0,
                "used_gb": 0,
                "free_gb": 0,
                "percent_used": 0,
                "ok": False,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------
    def check_memory(self) -> Dict[str, Any]:
        """
        Check memory usage by parsing /proc/meminfo (Linux).

        Returns:
            {total_mb, available_mb, percent_used, ok}
        """
        meminfo_path = Path("/proc/meminfo")
        if not meminfo_path.exists():
            return self._fallback_memory()

        try:
            content = meminfo_path.read_text(encoding="utf-8")
            mem = {}
            for line in content.strip().split("\n"):
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    # Value is in kB
                    val_parts = parts[1].strip().split()
                    if val_parts:
                        try:
                            mem[key] = int(val_parts[0])
                        except ValueError:
                            continue

            total_kb = mem.get("MemTotal", 0)
            available_kb = mem.get("MemAvailable", 0)

            # Fallback if MemAvailable not present (older kernels)
            if available_kb == 0:
                free_kb = mem.get("MemFree", 0)
                buffers_kb = mem.get("Buffers", 0)
                cached_kb = mem.get("Cached", 0)
                available_kb = free_kb + buffers_kb + cached_kb

            total_mb = round(total_kb / 1024, 1)
            available_mb = round(available_kb / 1024, 1)
            used_mb = round((total_kb - available_kb) / 1024, 1)
            percent_used = round(((total_kb - available_kb) / total_kb) * 100, 1) if total_kb > 0 else 0.0

            return {
                "total_mb": total_mb,
                "available_mb": available_mb,
                "used_mb": used_mb,
                "percent_used": percent_used,
                "ok": percent_used < self.memory_threshold,
            }
        except Exception as e:
            logger.error("Memory check failed: %s", e)
            return self._fallback_memory()

    def _fallback_memory(self) -> Dict[str, Any]:
        """Fallback memory check when /proc/meminfo is unavailable."""
        return {
            "total_mb": 0,
            "available_mb": 0,
            "used_mb": 0,
            "percent_used": 0,
            "ok": True,
            "error": "/proc/meminfo not available (non-Linux?)",
        }

    # ------------------------------------------------------------------
    # CPU
    # ------------------------------------------------------------------
    def check_cpu(self, sample_seconds: float = 1.0) -> Dict[str, Any]:
        """
        Check CPU usage by sampling /proc/stat (Linux).

        Takes two readings separated by sample_seconds to calculate usage.

        Returns:
            {percent_used, load_1m, load_5m, load_15m, ok}
        """
        stat_path = Path("/proc/stat")

        # Load averages (works on most Unix)
        try:
            load_1m, load_5m, load_15m = os.getloadavg()
        except OSError:
            load_1m = load_5m = load_15m = 0.0

        if not stat_path.exists():
            return {
                "percent_used": 0.0,
                "load_1m": round(load_1m, 2),
                "load_5m": round(load_5m, 2),
                "load_15m": round(load_15m, 2),
                "ok": True,
                "error": "/proc/stat not available (non-Linux?)",
            }

        try:
            idle1, total1 = self._read_cpu_stat(stat_path)
            time.sleep(sample_seconds)
            idle2, total2 = self._read_cpu_stat(stat_path)

            idle_delta = idle2 - idle1
            total_delta = total2 - total1

            if total_delta == 0:
                percent_used = 0.0
            else:
                percent_used = round((1.0 - idle_delta / total_delta) * 100, 1)

            return {
                "percent_used": percent_used,
                "load_1m": round(load_1m, 2),
                "load_5m": round(load_5m, 2),
                "load_15m": round(load_15m, 2),
                "ok": percent_used < self.cpu_threshold,
            }
        except Exception as e:
            logger.error("CPU check failed: %s", e)
            return {
                "percent_used": 0.0,
                "load_1m": round(load_1m, 2),
                "load_5m": round(load_5m, 2),
                "load_15m": round(load_15m, 2),
                "ok": True,
                "error": str(e),
            }

    def _read_cpu_stat(self, stat_path: Path) -> tuple:
        """Read aggregate CPU times from /proc/stat. Returns (idle, total)."""
        content = stat_path.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if line.startswith("cpu "):
                parts = line.split()
                # cpu user nice system idle iowait irq softirq steal guest guest_nice
                values = [int(v) for v in parts[1:]]
                idle = values[3] + (values[4] if len(values) > 4 else 0)  # idle + iowait
                total = sum(values)
                return idle, total
        return 0, 0

    # ------------------------------------------------------------------
    # Vault
    # ------------------------------------------------------------------
    def check_vault_access(self, vault_path: str) -> Dict[str, Any]:
        """
        Check that the vault directory is readable and writable.

        Returns:
            {readable, writable, ok, path}
        """
        vp = Path(vault_path)
        readable = False
        writable = False

        # Check readable
        try:
            if vp.exists() and vp.is_dir():
                list(vp.iterdir())
                readable = True
        except (PermissionError, OSError) as e:
            logger.warning("Vault not readable: %s", e)

        # Check writable
        if readable:
            test_file = vp / ".health_check_test"
            try:
                test_file.write_text("health_check", encoding="utf-8")
                test_file.unlink()
                writable = True
            except (PermissionError, OSError) as e:
                logger.warning("Vault not writable: %s", e)

        return {
            "readable": readable,
            "writable": writable,
            "ok": readable and writable,
            "path": str(vp),
        }

    # ------------------------------------------------------------------
    # API Connectivity
    # ------------------------------------------------------------------
    def check_api_connectivity(
        self, endpoints: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Check connectivity to API endpoints.

        Args:
            endpoints: List of {name, url} dicts. Defaults to common services.

        Returns:
            {results: {name: {reachable, latency_ms}}, all_ok}
        """
        if endpoints is None:
            endpoints = [
                {"name": "google", "url": "https://www.googleapis.com"},
                {"name": "github", "url": "https://api.github.com"},
            ]

        results = {}
        for ep in endpoints:
            name = ep["name"]
            url = ep["url"]
            try:
                start = time.time()
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "health-monitor/1.0")
                urllib.request.urlopen(req, timeout=10)
                latency_ms = round((time.time() - start) * 1000, 1)
                results[name] = {"reachable": True, "latency_ms": latency_ms}
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                results[name] = {"reachable": False, "latency_ms": 0, "error": str(e)}

        all_ok = all(r["reachable"] for r in results.values())
        return {"results": results, "all_ok": all_ok}

    # ------------------------------------------------------------------
    # Combined
    # ------------------------------------------------------------------
    def check_all(
        self,
        vault_path: str,
        disk_path: str = "/",
        endpoints: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Run all resource checks.

        Returns:
            {disk, memory, cpu, vault, apis, healthy}
        """
        disk = self.check_disk(disk_path)
        memory = self.check_memory()
        cpu = self.check_cpu()
        vault = self.check_vault_access(vault_path)
        apis = self.check_api_connectivity(endpoints)

        healthy = all([
            disk.get("ok", False),
            memory.get("ok", False),
            cpu.get("ok", False),
            vault.get("ok", False),
        ])

        return {
            "disk": disk,
            "memory": memory,
            "cpu": cpu,
            "vault": vault,
            "apis": apis,
            "healthy": healthy,
        }
