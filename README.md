# Kaspi Shop notifier

Минимальный однопроходный скрипт: получить заказы из Kaspi API, отправить уведомления о новых заказах в Telegram, сохранить факт обработки в SQLite и завершиться.

## Быстрый старт
1) Скопируйте `.env.example` в `.env` и заполните значения.  
2) Соберите образ: `docker compose build`.  
3) Запустите разово: `docker compose run --rm notifier`.

Логи идут в stdout. Повторный запуск безопасен: уже обработанные заказов не дублируются.

## Переменные окружения (`.env`)
- `KASPI_BASE_URL` + `KASPI_ORDERS_PATH` или `KASPI_ORDERS_URL` — адрес эндпоинта заказов.
- `KASPI_API_KEY` — токен доступа.
- `KASPI_ORDER_STATE` / `KASPI_ORDER_STATUS` / `KASPI_PAGE_SIZE` — опциональные query-параметры фильтрации.
- `TELEGRAM_BOT_TOKEN` — токен бота.
- `TELEGRAM_CHAT_ID` — ID или @username получателя.
- `DB_PATH` — путь к файлу SQLite (по умолчанию `/data/state.db`).
- `HTTP_TIMEOUT` — таймаут HTTP запросов в секундах (по умолчанию 10).
- `DRY_RUN` — `1` чтобы не отправлять уведомления и не писать в БД (только логи).
- `INITIAL_SYNC_MODE` — `mark_only` (по умолчанию) или `notify_all` для первого пустого запуска.
- `LOG_LEVEL` — `DEBUG` / `INFO` / `WARNING` / `ERROR`.
- `LOCK_FILE_PATH` — путь к лок-файлу (по умолчанию `/tmp/kaspi-notifier.lock`).
- `PROCESSED_RETENTION_DAYS` — опциональная очистка старых записей (например `180`), пусто — без очистки.

## Dry run
```
DRY_RUN=1 docker compose run --rm notifier
```
Увидите, какие уведомления были бы отправлены.

## Логи
Все сообщения в stdout. Для просмотра последних запусков:  
`docker compose run --rm notifier | tail -n 200`

## Структура данных и адаптация
- Вся нормализация ответа Kaspi в `app/kaspi_client.py` → `normalize_order(raw_order)`.  
- Если структура JSON меняется, поправьте только эту функцию.

## Как запускать раз в минуту на Oracle VM через systemd timer
1) Скопируйте репозиторий на VM, установите Docker + docker-compose-plugin.  
2) Пример unit `/etc/systemd/system/kaspi-notifier.service`:
```
[Unit]
Description=Kaspi notifier one-shot
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/kaspi-notifier
ExecStart=/usr/bin/docker compose run --rm notifier
```
3) Таймер `/etc/systemd/system/kaspi-notifier.timer`:
```
[Unit]
Description=Run kaspi notifier every minute

[Timer]
OnCalendar=*-*-* *:*:00
Unit=kaspi-notifier.service

[Install]
WantedBy=timers.target
```
4) `sudo systemctl daemon-reload && sudo systemctl enable --now kaspi-notifier.timer`

## Как избежать дублей уведомлений
- Все обработанные `order_id` сохраняются в SQLite (`processed_orders`), путь задается `DB_PATH`.  
- Общий volume `./data:/data` сохраняет состояние между запусками.  
- Повторный запуск безопасен: новые уведомления отправляются только для не сохранённых заказов.
- Если задано `PROCESSED_RETENTION_DAYS`, при старте удаляются записи старше указанного количества дней.

## Bootstrap и защита от дублей при первом запуске
- Если база пустая и `INITIAL_SYNC_MODE=mark_only` (по умолчанию), сервис пометит все найденные заказы обработанными без уведомлений и завершится.  
- Если `INITIAL_SYNC_MODE=notify_all`, при пустой базе отправятся уведомления по всем найденным заказам.

## Лок-файл
- По пути `LOCK_FILE_PATH` создаётся lock; при наличии lock второй процесс сразу завершается без работы.  
- Путь по умолчанию `/tmp/kaspi-notifier.lock`, можно переназначить на общий volume.

## Что внутри
- `app/main.py` — оркестратор одного прохода.  
- `app/kaspi_client.py` — запрос заказов, нормализация.  
- `app/storage.py` — работа с SQLite.  
- `app/telegram_client.py` — отправка сообщений в Telegram.  
- `app/config.py` — загрузка env.  
- `app/logger.py` — настройка stdout-логгера.  
- `app/models.py` — простой dataclass заказа.
