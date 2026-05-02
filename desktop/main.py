"""
Мониторинг конкурентов — desktop-оболочка: веб-интерфейс через QWebEngineView.

При старте проверяется /health. Если сервер не отвечает, из корня проекта
запускается subprocess: python run.py (тот же каталог, где лежит run.py).
Полный старый UI на PyQt: backup/old_main.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from io import TextIOBase
from pathlib import Path
from typing import TextIO

from PyQt6.QtCore import QObject, QThread, Qt, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QLabel,
    QSizePolicy,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView


def _api_port() -> int:
    raw = (os.environ.get("API_PORT") or "8000").strip()
    try:
        return int(raw)
    except ValueError:
        return 8000


API_PORT = _api_port()
WEB_UI_URL = f"http://127.0.0.1:{API_PORT}/"
HEALTH_URL = f"http://127.0.0.1:{API_PORT}/health"
BACKEND_CHECK_TIMEOUT_SEC = 2.0
BACKEND_WAIT_TOTAL_SEC = 30.0
BACKEND_POLL_INTERVAL_SEC = 0.45

# Рядом с desktop/main.py — вывод python run.py при автозапуске
BACKEND_STARTUP_LOG = Path(__file__).resolve().parent / "backend_startup.log"


def is_backend_available(url: str = HEALTH_URL, timeout: float = BACKEND_CHECK_TIMEOUT_SEC) -> bool:
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "CompetitorMonitor-Desktop/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return False


def resolve_project_root() -> Path | None:
    """Каталог с run.py и backend/ — из исходников или рядом с exe."""
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parent.parent

    cur = start
    for _ in range(10):
        if (cur / "run.py").is_file() and (cur / "backend").is_dir():
            return cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return None


def resolve_python_argv() -> list[str] | None:
    py = shutil.which("python")
    if py:
        return [py]
    if sys.platform == "win32" and shutil.which("py"):
        return ["py", "-3"]
    return None


def _popen_run_py(project_root: Path) -> tuple[subprocess.Popen | None, TextIO | None]:
    """Запуск python run.py; stdout и stderr пишутся в BACKEND_STARTUP_LOG (один файл)."""
    log_path = BACKEND_STARTUP_LOG
    argv_py = resolve_python_argv()
    if not argv_py:
        return None, None
    run_script = project_root / "run.py"
    if not run_script.is_file():
        return None, None
    cmd = [*argv_py, str(run_script)]

    creationflags = 0
    startupinfo = None
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    log_fp: TextIO | None = None
    try:
        log_fp = open(log_path, "w", encoding="utf-8", newline="\n")
        log_fp.write(
            "# Backend stdout/stderr (desktop autostart)\n"
            f"# Started: {datetime.now().isoformat(timespec='seconds')}\n"
            f"# cwd: {project_root}\n"
            f"# argv: {cmd!r}\n\n"
        )
        log_fp.flush()
    except OSError:
        if log_fp is not None:
            try:
                log_fp.close()
            except OSError:
                pass
        return None, None

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
    except OSError as e:
        try:
            log_fp.write(f"\n[desktop] subprocess.Popen failed: {e}\n")
            log_fp.flush()
        finally:
            try:
                log_fp.close()
            except OSError:
                pass
        return None, None

    return proc, log_fp


def _close_log_file(log_fp: TextIO | None) -> None:
    """Закрыть файловый объект лога после остановки backend (или при отмене запуска)."""
    if log_fp is None:
        return
    try:
        log_fp.flush()
    except OSError:
        pass
    try:
        log_fp.close()
    except OSError:
        pass


def _terminate_owned_backend(proc: subprocess.Popen | None) -> None:
    """Гасим процесс, запущенный desktop; на Windows — дерево (run.py + uvicorn reload)."""
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                timeout=12,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


class BackendBootstrapper(QObject):
    """В фоне: /health → при необходимости subprocess → снова /health."""

    ready = pyqtSignal()
    failed = pyqtSignal(str)
    subprocess_started = pyqtSignal(object)

    def __init__(self, health_url: str, project_root: Path | None) -> None:
        super().__init__()
        self._health_url = health_url
        self._project_root = project_root

    def run(self) -> None:
        if is_backend_available(self._health_url):
            self.ready.emit()
            return

        root = self._project_root or resolve_project_root()
        if root is None:
            self.failed.emit(
                "Не найден каталог проекта (нужны run.py и папка backend/).\n"
                "Для .exe положите программу внутрь каталога проекта или рядом с ним."
            )
            return

        proc, log_fp = _popen_run_py(root)
        log_resolved = str(BACKEND_STARTUP_LOG.resolve())
        if proc is None:
            self.failed.emit(
                "Не удалось запустить backend (python в PATH и файл run.py в корне проекта).\n"
                f"Если файл лога создан, смотрите:\n{log_resolved}\n\n"
                "Установите Python 3 или запустите сервер вручную: python run.py"
            )
            return

        self.subprocess_started.emit((proc, log_fp))

        deadline = time.monotonic() + BACKEND_WAIT_TOTAL_SEC
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                self.failed.emit(
                    "Процесс backend завершился при запуске.\n"
                    f"Причина — в выводе процесса. Откройте лог (обычно достаточно последних строк):\n{log_resolved}"
                )
                return
            if is_backend_available(self._health_url):
                self.ready.emit()
                return
            time.sleep(BACKEND_POLL_INTERVAL_SEC)

        self.failed.emit(
            f"Сервер не ответил на {self._health_url} за {int(BACKEND_WAIT_TOTAL_SEC)} сек.\n"
            f"Вывод backend записан в:\n{log_resolved}"
        )


class MainWindow(QMainWindow):
    """Одно окно, один QWebEngineView — URL задаётся после успешного /health."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Мониторинг конкурентов")
        self.setMinimumSize(1200, 800)
        self.resize(1280, 800)

        self._initial_navigation_done = False
        self._shutting_down = False
        self._backend_proc: subprocess.Popen | None = None
        self._backend_log_fp: TextIO | None = None
        self._owns_backend = False
        self._bootstrap_thread: QThread | None = None

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._loading_page = self._build_loading_page()
        self._error_page = self._build_error_page()
        self._stack.addWidget(self._loading_page)
        self._stack.addWidget(self._error_page)

        self._webview = QWebEngineView()
        self._stack.addWidget(self._webview)

        self._stack.setCurrentWidget(self._loading_page)
        self._start_bootstrap()

    def _build_loading_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        msg = QLabel("Подключение к серверу…")
        msg.setStyleSheet("font-size: 16px; color: #94a3b8;")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(msg)
        layout.addStretch(2)
        return page

    def _build_error_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        title = QLabel("Не удалось подключиться к серверу")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #f1f5f9;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._error_message = QLabel("")
        self._error_message.setStyleSheet("font-size: 14px; color: #94a3b8; line-height: 1.5;")
        self._error_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_message.setWordWrap(True)
        self._error_message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        retry = QPushButton("Повторить")
        retry.setFixedWidth(160)
        retry.clicked.connect(self._on_retry_clicked)
        retry.setStyleSheet(
            "QPushButton { padding: 10px 20px; background: #06b6d4; color: #0a0f1c; "
            "border: none; border-radius: 8px; font-weight: 600; }"
            "QPushButton:hover { background: #22d3ee; }"
        )

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(self._error_message)
        layout.addWidget(retry, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(2)
        return page

    def _set_error_text(self, text: str) -> None:
        self._error_message.setText(
            text + f"\n\nОжидается API: {HEALTH_URL}\nВеб-интерфейс: {WEB_UI_URL}"
        )

    def _flush_and_close_backend_log(self) -> None:
        _close_log_file(self._backend_log_fp)
        self._backend_log_fp = None

    def _cleanup_bootstrap_thread(self) -> None:
        if self._bootstrap_thread:
            self._bootstrap_thread.quit()
            self._bootstrap_thread.wait(3000)
            self._bootstrap_thread = None

    def _start_bootstrap(self) -> None:
        self._cleanup_bootstrap_thread()
        self._stack.setCurrentWidget(self._loading_page)

        thread = QThread()
        worker = BackendBootstrapper(HEALTH_URL, resolve_project_root())
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.ready.connect(self._on_backend_ready)
        worker.failed.connect(self._on_backend_failed)
        worker.subprocess_started.connect(self._on_subprocess_started)

        def _done() -> None:
            worker.deleteLater()
            thread.quit()

        worker.ready.connect(_done)
        worker.failed.connect(_done)
        thread.finished.connect(thread.deleteLater)

        self._bootstrap_thread = thread
        thread.start()

    def _on_subprocess_started(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        proc, log_fp = payload
        if not isinstance(proc, subprocess.Popen):
            if isinstance(log_fp, TextIOBase):
                _close_log_file(log_fp)
            return
        if self._shutting_down:
            if isinstance(log_fp, TextIOBase):
                _close_log_file(log_fp)
            _terminate_owned_backend(proc)
            return
        self._backend_proc = proc
        self._backend_log_fp = log_fp if isinstance(log_fp, TextIOBase) else None
        self._owns_backend = True

    def _on_backend_ready(self) -> None:
        if self._shutting_down:
            return
        self._try_open_web_ui(from_retry=False)

    def _on_backend_failed(self, message: str) -> None:
        if self._shutting_down:
            return
        if self._owns_backend:
            _terminate_owned_backend(self._backend_proc)
        self._flush_and_close_backend_log()
        self._backend_proc = None
        self._owns_backend = False
        self._set_error_text(message)
        self._stack.setCurrentWidget(self._error_page)

    def _on_retry_clicked(self) -> None:
        self._start_bootstrap()

    def _try_open_web_ui(self, *, from_retry: bool) -> None:
        if not is_backend_available():
            self._set_error_text("Сервер перестал отвечать на /health.")
            self._stack.setCurrentWidget(self._error_page)
            return

        if from_retry and self._initial_navigation_done:
            self._webview.reload()
        elif not self._initial_navigation_done:
            self._webview.setUrl(QUrl(WEB_UI_URL))
            self._initial_navigation_done = True

        self._stack.setCurrentWidget(self._webview)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._shutting_down = True
        self._cleanup_bootstrap_thread()
        if self._owns_backend:
            _terminate_owned_backend(self._backend_proc)
        self._flush_and_close_backend_log()
        self._backend_proc = None
        self._owns_backend = False
        event.accept()


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)
    app.setApplicationName("Competitor Monitor")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
