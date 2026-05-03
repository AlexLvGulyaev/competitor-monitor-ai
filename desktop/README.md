# Мониторинг конкурентов — Desktop

Нативное окно с **тем же веб-интерфейсом**, что и в браузере: **PyQt6** + **QWebEngineView**, загрузка UI по адресу **`http://127.0.0.1:{порт}/`** (по умолчанию порт **8000**, совпадает с `API_PORT` в backend).

Старый полностью нативный UI на PyQt лежит в `backup/old_main.py` и при обычном запуске не используется.

## Поведение при запуске

1. Запрос **`GET http://127.0.0.1:<порт>/health`** (порт из переменной окружения `API_PORT`, иначе 8000).
2. Если backend уже отвечает — сразу открывается веб-интерфейс.
3. Если нет — из **корня проекта** (каталог с `run.py` и `backend/`) автоматически запускается **`python run.py`** (subprocess, `cwd` — этот каталог).
4. Ожидание готовности по **`/health`** (таймаут порядка 30 с, опрос в цикле).
5. При закрытии приложения завершается **только** тот процесс backend, который был запущен desktop (внешний `python run.py` не трогается).
6. Вывод stdout/stderr автозапуска пишется в **`desktop/backend_startup.log`** (удобно при ошибках старта).

Ручной запуск backend (`python run.py` в отдельном терминале) остаётся **опциональным**: можно поднять сервер заранее или доверить автозапуск desktop.

## Требования

- Python 3.9+
- Зависимости из `desktop/requirements.txt` (PyQt6, PyQt6-WebEngine и др.)
- На части систем для Qt WebEngine желателен установленный **Google Chrome / Chromium**
- Для автозапуска backend: в **`PATH`** доступен интерпретатор **`python`** (или на Windows срабатывает **`py -3`**), а структура проекта с **`run.py`** обнаруживается относительно `desktop/main.py` или каталога `.exe`

## Быстрый старт

```bash
cd desktop
pip install -r requirements.txt
```

Запуск из **корня репозитория** (рядом с `run.py`):

```bash
python desktop/main.py
```

Либо из каталога `desktop`:

```bash
cd desktop
python main.py
```

Backend поднимется сам при необходимости. При желании сервер можно запустить вручную до desktop:

```bash
# из корня проекта (pem08)
python run.py
```

## Сборка .exe

```bash
cd desktop
python build.py
```

Либо: `pyinstaller CompetitorMonitor.spec`

Артефакт: **`dist/CompetitorMonitor.exe`**. Положите исполняемый файл так, чтобы при поиске вверх по каталогам находился корень проекта с **`run.py`** и **`backend/`** — иначе автозапуск backend недоступен (останется только сценарий с уже запущенным сервером и экраном ошибки с кнопкой «Повторить»).

## Структура

```
desktop/
├── main.py                  # Окно + WebEngine, health, автозапуск run.py
├── backend_startup.log      # Лог stdout/stderr backend при автозапуске (создаётся при необходимости)
├── backup/
│   └── old_main.py          # Прежний PyQt-интерфейс (архив)
├── styles.py                # Не используется в web-оболочке
├── api_client.py            # Не используется в web-оболочке
├── build.py
├── CompetitorMonitor.spec
├── requirements.txt
└── README.md
```
