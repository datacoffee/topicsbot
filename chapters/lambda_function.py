import os
import re
# import json
import boto3
# from eyed3.id3 import Tag
from datetime import datetime

TABLE = os.environ['DYNAMO_TABLE']
CHAPTERS_LENGHT = int(os.environ['CHAPTERS_LENGHT'])


def lambda_handler(event, context):
    if event['action'] == 'get_chapters':
        response = get_chapters(event['episode'])
    else:
        response = "Unknown command for Lambda render"
    return {'response': response}


def get_chapters(episode):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)
    key = boto3.dynamodb.conditions.Key('episode').eq(episode)
    items = table.query(
        KeyConditionExpression=key
    )
    response = '#,Name,Link,Start'
    for record in items['Items']:
        cnt = 0
        # getting last /record time
        prev_dttm = datetime.strptime(record['records'][-1], "%m/%d/%Y, %H:%M:%S")
        for item in record['news']:
            if len(item['chapters']) > 0:
                text, links = split_news(item['text'])
                link = links[0] if len(links) > 0 else ""
                # getting first chapter time
                dttm = datetime.strptime(item['chapters'][0], "%m/%d/%Y, %H:%M:%S")
                time_delta = dttm - prev_dttm
                cnt += 1
                response += f'\n"M{str(cnt)}","{cut_text(text)}","{link}","{format_time(time_delta)}"'
    return response


def split_news(news_str):
    links = re.findall(r'(https?://[^\s]+)', news_str)
    text = news_str.strip()
    for link in links:
        text = text.replace(link, '')
    text = re.sub(' +', ' ', text).strip().replace('"', "'")
    text = text[:1].upper() + text[1:]
    return (text, links)


def cut_text(text):
    if len(text) > CHAPTERS_LENGHT:
        text = text[:CHAPTERS_LENGHT-3].strip() + "..."
    return text


def format_time(tdelta):
    # days = tdelta.days
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}:00"


def get_id(dttm_str):
    dttm = datetime.strptime(dttm_str, "%m/%d/%Y, %H:%M:%S")
    return dttm.strftime("%Y%m%d%H%M%S")
