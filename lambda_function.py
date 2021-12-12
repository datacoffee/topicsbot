import os
import json
import boto3
import urllib3
import gspread
from datetime import datetime

TOKEN = os.environ['TELEGRAM_TOKEN']
CHANNEL = os.environ['NEWS_CHANNEL']
TABLE = os.environ['DYNAMO_TABLE']
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
GCP_JSON = json.loads(os.environ['GCP_JSON'])
GCP_SPREADSHEET = os.environ['GCP_SPREADSHEET']
GCP_WORKSHEET = os.environ['GCP_WORKSHEET']
GCP_START_ROW = os.environ['GCP_START_ROW']
GCP_DATE_COLUMN = os.environ['GCP_DATE_COLUMN']
GCP_AUTHOR_COLUMN = os.environ['GCP_AUTHOR_COLUMN']
GCP_NEWS_COLUMN = os.environ['GCP_NEWS_COLUMN']


def lambda_handler(event, context):
    try:
        chat_id = event["message"]["chat"]["id"]
        message = event["message"]
        
        if str(chat_id) != CHANNEL:
            # response = f"Chat {chat_id} is not allowed"
            return {"statusCode": 404}
        elif message["text"].startswith("/list"):
            response = get_list(message["text"])
        elif message["text"].startswith("/gsheet"):
            response = export_to_spreadsheet()
        elif message["text"].startswith("/episode"):
            response = episode(message)
        elif message["text"].startswith("/restore"):
            response = restore(message)
        elif "#news" in message["text"] and message["text"].strip() != "#news":
            response = save_news(message)
        elif message["text"].startswith("/delete "):
            response = delete(message)
        elif message["text"].startswith("/record"):
            response = chapter(message)
        elif message["text"].startswith("/chapter_"):
            response = chapter(message)
        
        if response:
            http = urllib3.PoolManager()
            s = response
            n = 4096
            for response_chunk in [s[k:k+n] for k in range(0, len(s), n)]:
                data = {
                    "text": response_chunk,
                    "chat_id": chat_id,
                    "parse_mode": 'HTML',
                    'disable_web_page_preview': True
                }
                encoded_data = json.dumps(data).encode('utf-8')
                url = BASE_URL + "/sendMessage"
                resp = http.request('POST',
                                    url,
                                    headers={'Content-Type': 'application/json'},
                                    body=encoded_data)
    except Exception as e:
        print(f"An error occurred: {e}")
    return {"statusCode": 200}


def get_list(message):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    words = message.split(' ')
    episode = words[1] if len(words) == 2 else 'next'
    key = boto3.dynamodb.conditions.Key('episode').eq(episode)
    items = table.query(
        KeyConditionExpression=key
    )
    response = f'News for episode {episode}'
    for authors in items['Items']:
        response += f"\n from @{authors['author']}"
        for item in authors['news']:
            response += f"\n- /chapter_{get_id(item['added'])}, {item['text']}"
        response += "\n"
    return response


def export_to_spreadsheet():
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(TABLE)
        key = boto3.dynamodb.conditions.Key('episode').eq('next')
        items = table.query(
            KeyConditionExpression=key
        )
        gc = gspread.service_account_from_dict(GCP_JSON)
        sh = gc.open(GCP_SPREADSHEET)
        worksheet = sh.worksheet(GCP_WORKSHEET)
        current_row = int(GCP_START_ROW)
        for authors in items['Items']:
            for item in authors['news']:
                # worksheet.update(f'{GCP_DATE_COLUMN}{str(current_row)}', item['added'])
                worksheet.update(f'{GCP_AUTHOR_COLUMN}{str(current_row)}', f"@{authors['author']}")
                worksheet.update(f'{GCP_NEWS_COLUMN}{str(current_row)}', item['text'])
                current_row += 1
        response = 'News list was exported to Google spreadsheet'
    except Exception as e:
        response = f'Error: {e}'
    return response


def save_news(message):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    item = table.get_item(
        Key={
            "episode": "next",
            "author": message["from"]["username"]
        }
    )
    if 'Item' in item:
        item = item['Item']
        item['news'].append(
            {
                "added": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
                "text": message["text"].replace('#news', '')
            }
        )
    else:
        item = {
            "episode": "next",
            "author": message["from"]["username"],
            "news": [
                {
                    "added": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
                    "text": message["text"].replace('#news', '')
                }
            ]
        }
    resp = table.put_item(Item=item)
    if "ResponseMetadata" in resp.keys() and resp["ResponseMetadata"]["HTTPStatusCode"] == 200:
        response = "Saved!"
    else:
        print(resp)
        response = "Saving Error!"
    return response


def episode(message):
    words = message['text'].split(' ')
    if len(words) == 1:
        response = 'Episode # must be specified'
    else:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(TABLE)
        key = boto3.dynamodb.conditions.Key('episode').eq('next')
        items = table.query(
            KeyConditionExpression=key
        )
        episode = ' '.join(words[1:])
        for item in items['Items']:
            table.delete_item(
                Key={
                    "episode": item['episode'],
                    "author": item['author']
                }
            )
            item['episode'] = episode
            table.put_item(Item=item)
            response = f'News saved for episode {episode}'
    return response


def restore(message):
    words = message['text'].split(' ')
    if len(words) == 1:
        response = 'Episode # must be specified'
    else:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(TABLE)
        episode = ' '.join(words[1:])
        key = boto3.dynamodb.conditions.Key('episode').eq(episode)
        items = table.query(
            KeyConditionExpression=key
        )
        for item in items['Items']:
            table.delete_item(
                Key={
                    "episode": item['episode'],
                    "author": item['author']
                }
            )
            item['episode'] = 'next'
            table.put_item(Item=item)
            response = 'News restored'
    return response


def delete(message):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    key = boto3.dynamodb.conditions.Key('episode').eq('next')
    items = table.query(
        KeyConditionExpression=key
    )
    response = ''
    for authors in items['Items']:
        for item in authors['news']:
            if item['added'] == message["text"].replace('/delete ', ''):
                response += 'Deleted: ' + item['text'] + '\n'
                authors['news'].remove(item)
                resp = table.put_item(Item=authors)
    if "ResponseMetadata" in resp.keys() and resp["ResponseMetadata"]["HTTPStatusCode"] == 200:
        response += "Done!"
    else:
        response = "Can't save changes!"
    return response


def get_id(dttm_str):
    dttm = datetime.strptime(dttm_str, "%m/%d/%Y, %H:%M:%S")
    return dttm.strftime("%Y%m%d%H%M%S")


def get_dttm_from_id(news_id):
    dttm = datetime.strptime(news_id, "%Y%m%d%H%M%S")
    return dttm.strftime("%m/%d/%Y, %H:%M:%S")


def chapter(message):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    item = table.get_item(
        Key={
            "episode": "next",
            "author": "@chapters"
        }
    )
    news_id = message["text"].replace('/chapter_', '').replace('/record', '')
    dttm = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    if 'Item' in item:
        item = item['Item']
        item['chapters'].append(
            {
                "added": dttm,
                "news_id": news_id
            }
        )
    else:
        item = {
            "episode": "next",
            "author": "@chapters",
            "chapters": [
                {
                    "added": dttm,
                    "news_id": news_id
                }
            ]
        }
    table.put_item(Item=item)
    if news_id:
        response = f'Chapter {news_id} at {dttm})'
    else:
        response = f'Recording has been started, {dttm}'
    return response
