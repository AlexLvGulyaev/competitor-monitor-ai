"""
Скрипт сборки .exe файла для Windows (QWebEngineView + веб-UI).
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path


def build_exe():
    """Собрать .exe файл"""
    print("=" * 60)
    print("СБОРКА DESKTOP ПРИЛОЖЕНИЯ (WebEngine)")
    print("=" * 60)

    current_dir = Path(__file__).parent

    print("\nПроверка PyInstaller...")
    try:
        import PyInstaller
        print(f"   OK PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("   PyInstaller не установлен: pip install pyinstaller")
        sys.exit(1)

    app_name = "CompetitorMonitor"

    pyinstaller_args = [
        "pyinstaller",
        "--name", app_name,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        # Ресурсы Qt WebEngine (процесс, переводы, и т.д.)
        "--collect-all", "PyQt6.QtWebEngineCore",
        "--collect-all", "PyQt6.QtWebEngineWidgets",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtWebEngineWidgets",
        "--hidden-import", "PyQt6.QtWebEngineCore",
        "--hidden-import", "PyQt6.QtWebChannel",
        "main.py",
    ]

    print(f"\nЗапуск сборки: {app_name}.exe")
    print("-" * 60)

    result = subprocess.run(pyinstaller_args, cwd=current_dir)

    if result.returncode == 0:
        exe_path = current_dir / "dist" / f"{app_name}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 60)
            print("СБОРКА ЗАВЕРШЕНА")
            print("=" * 60)
            print(f"\nФайл: {exe_path}")
            print(f"Размер: {size_mb:.1f} MB")
            print("\nЗапуск:")
            print("   1. Backend: python run.py (из корня pem08)")
            print(f"   2. {app_name}.exe")
        else:
            print("\nОшибка: .exe не найден")
    else:
        print("\nОшибка сборки")
        sys.exit(1)


def clean():
    """Очистить артефакты сборки"""
    current_dir = Path(__file__).parent
    dirs_to_remove = ["build", "dist", "__pycache__"]
    print("Очистка...")
    for dir_name in dirs_to_remove:
        dir_path = current_dir / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"   удалено: {dir_name}/")
    print("Готово")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
    else:
        build_exe()
