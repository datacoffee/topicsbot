import os
import re
import json
import boto3
import urllib3
import gspread
from datetime import datetime

TOKEN = os.environ['TELEGRAM_TOKEN']
CHANNEL = os.environ['NEWS_CHANNEL']
TABLE = os.environ['DYNAMO_TABLE']
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
LAMBDA_DIGEST = os.environ['LAMBDA_DIGEST']
LAMBDA_CHAPTERS = os.environ['LAMBDA_CHAPTERS']
GCP_JSON = json.loads(os.environ['GCP_JSON'])
GCP_SPREADSHEET = os.environ['GCP_SPREADSHEET']
GCP_WORKSHEET = os.environ['GCP_WORKSHEET']
GCP_START_ROW = os.environ['GCP_START_ROW']
GCP_DATE_COLUMN = os.environ['GCP_DATE_COLUMN']
GCP_AUTHOR_COLUMN = os.environ['GCP_AUTHOR_COLUMN']
GCP_NEWS_COLUMN = os.environ['GCP_NEWS_COLUMN']
GCP_LINKS_COLUMN = os.environ['GCP_LINKS_COLUMN']
GSHEET_LINK = os.environ['GSHEET_LINK']


def lambda_handler(event, context):
    try:
        chat_id = event["message"]["chat"]["id"]
        message = event["message"]
        thread_id = message["message_thread_id"] if "message_thread_id" in message else False
        
        if str(chat_id) != CHANNEL:
            # response = f"Chat {chat_id} is not allowed\n"
            # response += str(event["message"])
            return {"statusCode": 404}
        elif "#news" in message["text"] and message["text"].strip() != "#news":  # WORKS
            response = save_news(message)
        elif message["text"].startswith("/list"):
            cmd = message["text"].split()
            response = get_list(cmd[1].strip() if len(cmd) > 1 else 'next')
        elif message["text"].startswith("/gsheet"):
            response = export_to_spreadsheet()
        elif message["text"].startswith("/episode"):
            cmd = message["text"].split()
            response = move_episode('next', cmd[1].strip() if len(cmd) > 1 else 'next')
        elif message["text"].startswith("/restore"):
            cmd = message["text"].split()
            response = move_episode(cmd[1].strip() if len(cmd) > 1 else 'next', 'next')
        elif message["text"].startswith("/delete_"):
            news_id = message["text"].replace('/delete_', '').split('@')[0]
            response = delete(news_id)
        elif message["text"].startswith("/record"):
            response = get_list('next')
            response += chapter()
        elif message["text"].startswith("/chapter_"):
            news_id = message["text"].replace('/chapter_', '').split('@')[0]
            response = get_list('next', news_id)
            response += chapter(news_id)
        elif message["text"].startswith("/digest"):
            response = invoke_lambda(LAMBDA_DIGEST, 'digest')
        elif message["text"].startswith("/get_chapters"):
            response = invoke_lambda(LAMBDA_CHAPTERS, 'get_chapters')
        
        if response:
            http = urllib3.PoolManager()
            response_chunks = split_long_string(response)
            for chunk in response_chunks:
                data = {
                    "text": chunk,
                    "chat_id": chat_id,
                    "parse_mode": 'HTML',
                    'disable_web_page_preview': True
                }
                if thread_id:
                    data["message_thread_id"] = thread_id
                encoded_data = json.dumps(data).encode('utf-8')
                url = BASE_URL + "/sendMessage"
                resp = http.request('POST',
                                    url,
                                    headers={'Content-Type': 'application/json'},
                                    body=encoded_data)
    except Exception as e:
        print(f"An error occurred: {e}")
    return {"statusCode": 200}


def get_list(episode='next', curr_news_id=None):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    key = boto3.dynamodb.conditions.Key('episode').eq(episode)
    items = table.query(
        KeyConditionExpression=key
    )
    discussed = []
    current = []
    not_discussed = []
    for record in items['Items']:
        for item in record['news']:
            item['text'] = item['text'].replace('\n', ' ')
            news_str = '§'
            if get_id(item['added']) == curr_news_id:
                news_str += f"\n\n👉<b> {item['text']}</b>"
                current.append(news_str)
            elif len(item['chapters']) == 0:
                news_str += f"\n\n- /chapter_{get_id(item['added'])}, /delete_{get_id(item['added'])}, {item['text']}"
                not_discussed.append(news_str)
            else:
                news_str += f"\n<i><strike>- {item['text']}</strike></i>"
                discussed.append(news_str)
    response = f'Episode: {episode}'
    for news_str in discussed + current + not_discussed:
        response += news_str
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
        
        all_dates: list[list[str]] = list()
        all_authors: list[list[str]] = list()
        all_news_texts: list[list[str]] = list()
        all_news_links: list[list[str]] = list()

        for item in items['Items'][0]['news']:
            all_dates.append([item['added']])
            all_authors.append([f"@{item['author']}"])
            news_value: str = item['text']
            news_text, links = split_news(news_value)
            all_news_texts.append([news_text])
            all_news_links.append([' '.join(links)])

        column_len: int = len(items['Items'][0]['news'])
        end_row: int = int(GCP_START_ROW) + column_len
        
        dates_update_range = f'{GCP_DATE_COLUMN}{GCP_START_ROW}:{GCP_DATE_COLUMN}{end_row}'
        worksheet.update(f'{dates_update_range}', all_dates)
        
        author_update_range = f'{GCP_AUTHOR_COLUMN}{GCP_START_ROW}:{GCP_AUTHOR_COLUMN}{end_row}'
        worksheet.update(f'{author_update_range}', all_authors)
        
        news_update_range = f'{GCP_NEWS_COLUMN}{GCP_START_ROW}:{GCP_NEWS_COLUMN}{end_row}'
        worksheet.update(f'{news_update_range}', all_news_texts)
        
        links_update_range = f'{GCP_LINKS_COLUMN}{GCP_START_ROW}:{GCP_LINKS_COLUMN}{end_row}'
        worksheet.update(f'{links_update_range}', all_news_links)
        
        response = f'News list was exported to Google spreadsheet: {GSHEET_LINK}'
    except Exception as e:
        response = f'Error: {e}'
    return response


def save_news(message):
    news = message["text"].replace('#news', '').strip()
    dttm = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    item = table.get_item(
        Key={
            "episode": "next"
        }
    )
    if 'Item' in item:
        item = item['Item']
        item['news'].append(
            {
                "added": dttm,
                "text": news,
                "author": message["from"]["username"],
                "chapters": []
            }
        )
    else:
        item = {
            "episode": "next",
            "records": [],
            "news": [
                {
                    "added": dttm,
                    "text": news,
                    "author": message["from"]["username"],
                    "chapters": []
                }
            ]
        }
    table.put_item(Item=item)
    return 'Saved!'


def move_episode(ep_from, ep_to):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    key = boto3.dynamodb.conditions.Key('episode').eq(ep_from)
    items = table.query(
        KeyConditionExpression=key
    )
    for item in items['Items']:
        table.delete_item(
            Key={
                "episode": item['episode']
            }
        )
        item['episode'] = ep_to
        table.put_item(Item=item)
    response = f'News moved from {ep_from} to {ep_to}'
    return response


def delete(news_id):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    key = boto3.dynamodb.conditions.Key('episode').eq('next')
    items = table.query(
        KeyConditionExpression=key
    )
    for authors in items['Items']:
        for item in authors['news']:
            if get_id(item['added']) == news_id:
                authors['news'].remove(item)
                table.put_item(Item=authors)
                response = 'Deleted: ' + item['text']
    if 'response' not in locals():
        response = 'Cannot find news to delete OR there was an error'
    return response


def get_id(dttm_str):
    dttm = datetime.strptime(dttm_str, "%m/%d/%Y, %H:%M:%S")
    return dttm.strftime("%Y%m%d%H%M%S")


def get_dttm_from_id(news_id):
    dttm = datetime.strptime(news_id, "%Y%m%d%H%M%S")
    return dttm.strftime("%m/%d/%Y, %H:%M:%S")


def chapter(news_id=None):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    key = boto3.dynamodb.conditions.Key('episode').eq('next')
    items = table.query(
        KeyConditionExpression=key
    )
    dttm = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    if news_id:
        for record in items['Items']:
            if len(record['records']) > 0:
                for item in record['news']:
                    if get_id(item['added']) == news_id:
                        # response = item['text']
                        item['chapters'].append(dttm)
                        table.put_item(Item=record)
                        response = f'Chapter {news_id} started at {dttm}'
            else:
                response = 'Firstly, record should be started with /record'
    else:
        for record in items['Items']:
            record['records'].append(dttm)
            table.put_item(Item=record)
        response = f'Recording started at {dttm}'
    response = '\n\n' + response
    return response


def invoke_lambda(arn, cmd):
    client = boto3.client('lambda')
    inputParams = {
        "episode": "next",
        "action": cmd
    }
    response = client.invoke(
        FunctionName=arn,
        InvocationType='RequestResponse',
        Payload=json.dumps(inputParams)
    )

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return json.loads(response['Payload'].read())['response']
    else:
        return "Error in Lambda invocation"

def split_news(news_str):
    links = re.findall(r'(https?://[^\s]+)', news_str)
    text = news_str.strip()
    for link in links:
        text = text.replace(link, '')
    text = re.sub(' +', ' ', text).strip().replace('"', "'")
    text = text[:1].upper() + text[1:]
    return (text, links)

def split_long_string(text, max_chunk_length=4096):
    words = text.split('§')  # Split the text into individual words
    chunks = []
    current_chunk = []

    for word in words:
        if len(' '.join(current_chunk + [word])) <= max_chunk_length:
            current_chunk.append(word)
        else:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks
