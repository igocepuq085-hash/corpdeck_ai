# AI Brand Deck Studio

## Локальный запуск

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Railway

Переменные окружения:

```text
OPENAI_API_KEY
OPENAI_TEXT_MODEL
OPENAI_IMAGE_MODEL
```

Start command:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## OpenAI API

Для AI-генерации плана создайте `.env` и укажите:

```text
OPENAI_API_KEY=...
OPENAI_TEXT_MODEL=gpt-5.5
```

Если ключ не задан, сервис работает в локальном fallback-режиме.

## PNG-визуалы

Сервис генерирует не большие фоновые картинки, а точечные PNG-элементы:

- иконки;
- мини-иллюстрации;
- тематические акценты.

Они подбираются по теме пояснительной записки и по смыслу конкретных слайдов.
Файлы сохраняются в:

```text
static/generated/{project_id}/
```

Для работы укажите:

```text
OPENAI_API_KEY=...
OPENAI_IMAGE_MODEL=gpt-image-1
```

Минимальный FastAPI-проект для онлайн-сервиса генерации и улучшения корпоративных презентаций.

## Запуск на Windows

Создайте виртуальное окружение:

```powershell
python -m venv .venv
```

Активируйте окружение:

```powershell
.\.venv\Scripts\Activate.ps1
```

Установите зависимости:

```powershell
pip install -r requirements.txt
```

Запустите приложение:

```powershell
uvicorn main:app --reload
```

Откройте в браузере:

```text
http://127.0.0.1:8000
```

## Логотип

Основной логотип хранится в:

```text
static/brand/logo.png
```

Файл `logo.png` должен быть добавлен в GitHub-репозиторий вместе с проектом.

## Фирменный стиль

В проект добавлен брендбук презентаций:

- основная палитра: `#0077C8`, `#003D73`, `#66B5E8`, `#CFE6F7`, `#7D8793`, `#2B2F36`, `#FFFFFF`;
- основной фон слайдов: светлый фирменный градиент;
- логотип: `static/brand/logo.png`;
- слайды используют координатный мастер-шаблон `1600x900`;
- все таблицы, графики, карточки и footer оформляются в единой системе.
