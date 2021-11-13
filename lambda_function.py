import os
import json
import boto3
import urllib3
from datetime import datetime

TOKEN = os.environ['TELEGRAM_TOKEN']
CHANNEL = os.environ['NEWS_CHANNEL']
TABLE = os.environ['DYNAMO_TABLE']
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


def lambda_handler(event, context):
    try:
        chat_id = event["message"]["chat"]["id"]
        message = event["message"]
        
        if str(chat_id) != CHANNEL:
            # response = f"Chat {chat_id} is not allowed"
            return {"statusCode": 404}
        elif message["text"].startswith("/list"):
            response = get_list()
        elif message["text"].startswith("/episode "):
            response = episode(message)
        elif "#news" in message["text"] and message["text"].strip() != "#news":
            response = save_news(message)
        elif message["text"].startswith("/delete "):
            response = delete(message)
        
        if response:
            http = urllib3.PoolManager()
            print(response)
            data = {
                "text": response,
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


def get_list():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    key = boto3.dynamodb.conditions.Key('episode').eq('next')
    items = table.query(
        KeyConditionExpression=key
    )
    response = 'News'
    for authors in items['Items']:
        response += f"\n from @{authors['author']}"
        for item in authors['news']:
            response += f"\n- {item['added']}, {item['text'][:30]}..."
    response += ''
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
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    key = boto3.dynamodb.conditions.Key('episode').eq('next')
    items = table.query(
        KeyConditionExpression=key
    )
    
    ep_num = message['text'].replace("/episode ", '')
    if ep_num.strip() == '':
        response = 'Episode # must be specified'
    for item in items['Items']:
        table.delete_item(
            Key={
                "episode": item['episode'],
                "author": item['author']
            }
        )
        item['episode'] = ep_num
        table.put_item(Item=item)
        response = f'News saved for episode #{ep_num}'
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
