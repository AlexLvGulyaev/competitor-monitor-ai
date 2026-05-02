# Мониторинг конкурентов — Desktop

Нативное окно Windows с **тем же веб-интерфейсом**, что и в браузере: внутри используется **QWebEngineView** и адрес `http://127.0.0.1:8000/`.

Старый полностью нативный UI на PyQt сохранён в `backup/old_main.py` (не используется при обычном запуске).

## Требования

- Python 3.9+
- Установленный **Google Chrome / Chromium** (для движка Qt WebEngine на части систем)
- Запущенный backend из корня проекта (`python run.py`)

## Быстрый старт

```bash
cd desktop
pip install -r requirements.txt
```

Сначала backend:

```bash
# из корня pem08:
python run.py
```

Затем desktop:

```bash
cd desktop
python main.py
```

Если сервер не запущен, показывается сообщение с подсказкой запустить `python run.py` и кнопка «Повторить».

## Сборка .exe

```bash
cd desktop
python build.py
```

Либо: `pyinstaller CompetitorMonitor.spec`

Готовый файл: `dist/CompetitorMonitor.exe`. Перед запуском `.exe` по-прежнему нужен запущенный backend.

## Структура

```
desktop/
├── main.py              # Окно + WebEngine → веб-UI
├── backup/
│   └── old_main.py      # Прежний PyQt-интерфейс (архив)
├── styles.py            # Не используется в web-оболочке (оставлено для old_main)
├── api_client.py        # Не используется в web-оболочке (оставлено для old_main)
├── build.py
├── CompetitorMonitor.spec
├── requirements.txt
└── README.md
```
