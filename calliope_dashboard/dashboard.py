"""Notebook-friendly lifecycle for one Calliope dashboard server."""

from __future__ import annotations

import atexit
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Any

import xarray as xr


class CalliopeDashboard:
    """Serve one Calliope solution in a local background dashboard.

    The solution may come from any solved Calliope model. ``from_pareto`` is an
    optional convenience constructor for selecting one multi-objective result.
    The model factory supplies the corresponding model inputs and metadata.
    """

    def __init__(
        self,
        *,
        model_factory: Callable[[], Any],
        solution: xr.Dataset,
        metadata: dict[str, Any] | None = None,
        host: str = "127.0.0.1",
        port: int = 8050,
        data_dir: str | Path | None = None,
    ) -> None:
        if not isinstance(solution, xr.Dataset):
            raise TypeError("solution must be an xarray.Dataset")
        if not 1 <= int(port) <= 65535:
            raise ValueError("port must be between 1 and 65535")

        self.model_factory = model_factory
        self.solution = solution
        self.metadata = dict(metadata or {})
        self.host = host
        self.port = int(port)
        self._requested_data_dir = Path(data_dir).resolve() if data_dir else None
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._data_dir: Path | None = None
        self._process: subprocess.Popen[str] | None = None
        self._log_handle: Any | None = None
        atexit.register(self.stop)

    @classmethod
    def from_pareto(
        cls,
        *,
        result: Any,
        point_id: int,
        model_factory: Callable[[], Any],
        **kwargs: Any,
    ) -> CalliopeDashboard:
        """Create a dashboard for one point from a ``ParetoResult``."""
        solution = result.solution(point_id)
        matching = result.points.loc[result.points["point_id"] == point_id]
        if matching.empty:
            raise KeyError(f"Unknown Pareto point_id: {point_id}")
        row = matching.iloc[0].to_dict()
        metadata = {
            "pareto_method": str(result.method),
            "pareto_point_id": int(point_id),
            "pareto_point": row,
        }
        return cls(
            model_factory=model_factory,
            solution=solution,
            metadata=metadata,
            **kwargs,
        )

    @property
    def url(self) -> str:
        """Local URL used by the dashboard server."""
        return f"http://{self.host}:{self.port}"

    @property
    def data_dir(self) -> Path | None:
        """Directory containing the generated dashboard NetCDF files."""
        return self._data_dir

    @property
    def is_running(self) -> bool:
        """Whether the background server process is alive."""
        return self._process is not None and self._process.poll() is None

    def prepare(self) -> Path:
        """Create dashboard-ready NetCDF files without solving the model."""
        if self.is_running:
            raise RuntimeError("Stop the dashboard before replacing its data.")

        if self._requested_data_dir is None:
            if self._temporary_directory is None:
                self._temporary_directory = tempfile.TemporaryDirectory(
                    prefix="calliope-dashboard-"
                )
            data_dir = Path(self._temporary_directory.name)
        else:
            data_dir = self._requested_data_dir
            data_dir.mkdir(parents=True, exist_ok=True)

        model = self.model_factory()
        model.results = self.solution.copy(deep=False)
        scalar_metadata = {
            key: value
            for key, value in self.metadata.items()
            if isinstance(value, (str, int, float, bool))
        }
        model.results.attrs.update(scalar_metadata)

        planning_path = data_dir / "planning.nc"
        operate_path = data_dir / "operate.nc"
        model.to_netcdf(planning_path)
        shutil.copy2(planning_path, operate_path)
        (data_dir / "selection.json").write_text(
            json.dumps(self.metadata, indent=2, default=str),
            encoding="utf-8",
        )
        self._data_dir = data_dir
        return data_dir

    def start(
        self,
        *,
        open_browser: bool = False,
        timeout: float = 20.0,
        default_tab: str = "results_planning",
    ) -> str:
        """Start the background server and return its local URL."""
        if self.is_running:
            return self.url
        data_dir = self.prepare()
        log_path = data_dir / "dashboard.log"
        self._log_handle = log_path.open("w", encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "calliope_dashboard._server",
            "--model-dir",
            str(data_dir),
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--default-tab",
            default_tab,
        ]
        self._process = subprocess.Popen(
            command,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                break
            try:
                with urllib.request.urlopen(self.url, timeout=0.5) as response:
                    if response.status == 200:
                        print(f"Calliope dashboard: {self.url}")
                        if open_browser:
                            webbrowser.open(self.url)
                        return self.url
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)

        self.stop()
        details = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(
            f"Dashboard did not start at {self.url}. Log: {log_path}\n{details}"
        )

    def stop(self) -> None:
        """Stop the background server; safe to call more than once."""
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self._process = None
        self._close_log()

    def _close_log(self) -> None:
        if self._log_handle is not None and not self._log_handle.closed:
            self._log_handle.close()
        self._log_handle = None

    def __enter__(self) -> CalliopeDashboard:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()
