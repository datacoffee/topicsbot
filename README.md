# topicsbot

Бот для сбора новостей в Telegram-чате

Работает через AWS Lambda, данные сохраняет в AWS DynamoDB

### Обязательные параметры Lambda
DYNAMO_TABLE - таблица для сохранения данных
TELEGRAM_TOKEN - API-токен от бота из BotFather
NEWS_CHANNEL - ID чата/группы на сообщения которой будет реагировать