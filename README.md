# topicsbot

Бот для сбора новостей в Telegram-чате

Работает через AWS Lambda, данные сохраняет в AWS DynamoDB

### Обязательные параметры Lambda

DYNAMO_TABLE - таблица для сохранения данных

TELEGRAM_TOKEN - API-токен от бота из BotFather

NEWS_CHANNEL - ID чата/группы на сообщения которой будет реагировать

GCP_JSON - JSON-строка с данными для подключения к GCP

GCP_SPREADSHEET - имя spreadsheet, к которому у бота есть доступ на редактирование

GCP_WORKSHEET - лист в spreadsheet

GCP_START_ROW - начальная строка для вставки

GCP_DATE_COLUMN - столбец для дат

GCP_AUTHOR_COLUMN - столбец для автора

GCP_NEWS_COLUMN - столбец для текста новости
