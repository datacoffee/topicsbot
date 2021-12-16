import os
# import json
import boto3
# from eyed3.id3 import Tag
from datetime import datetime

TABLE = os.environ['DYNAMO_TABLE']


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
    prev_dttm = datetime.now()
    for chapters in [x for x in items['Items'] if 'chapters' in x.keys()]:
        for item in chapters['chapters']:
            text, links = split_news(get_text(items, item['news_id']))
            dttm = datetime.strptime(item['added'], "%m/%d/%Y, %H:%M:%S")
            if item['news_id'] == "":
                time_delta = dttm - dttm
                cnt = 0
                # considering only last /record command
                response = f"\nM{str(cnt)},{text[:50]},{links[0]},{format_time(time_delta)}" 
            else:
                time_delta = dttm - prev_dttm
                cnt += 1
                response += f"\nM{str(cnt)},{text[:50]},{links[0]},{format_time(time_delta)}"
            prev_dttm = dttm
    return '#,Name,Link,Start' + response


def split_news(news_str):
    text = news_str.strip()
    links = [""]
    return (text, links)


def format_time(tdelta):
    # days = tdelta.days
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}:00"


def get_text(items, newsid):
    response = "Introduction"
    for authors in [x for x in items['Items'] if 'news' in x.keys()]:
        for item in authors['news']:
            if get_id(item['added']) == newsid:
                response = item['text']
    return response


def get_id(dttm_str):
    dttm = datetime.strptime(dttm_str, "%m/%d/%Y, %H:%M:%S")
    return dttm.strftime("%Y%m%d%H%M%S")
