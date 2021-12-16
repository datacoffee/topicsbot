import os
import re
import boto3
from github import Github
from datetime import datetime

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
GITHUB_REPO = os.environ['GITHUB_REPO']
GITHUB_BRANCH = os.environ['GITHUB_BRANCH']
TABLE = os.environ['DYNAMO_TABLE']
PUB_DTTM = datetime.now()


def lambda_handler(event, context):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)

    content = f"""
+++
categories = ["digest"]
date = "{PUB_DTTM.strftime("%Y-%m-%d")}"
description = "Дайджест новостей"
featured = "pic01.jpg"
featuredalt = ""
featuredpath = "date"
linktitle = ""
title = "Дайджест новостей от {PUB_DTTM.strftime("%d.%m.%Y")}"
slug = "news-digest-{PUB_DTTM.strftime("%d%m%Y")}"
type = "post"
+++

#### Приготовлен ведущими подкаста Data Coffee :)

"""

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE)

    episode = event['episode']
    key = boto3.dynamodb.conditions.Key('episode').eq(episode)
    items = table.query(
        KeyConditionExpression=key
    )
    for authors in [x for x in items['Items'] if 'news' in x.keys()]:
        for item in authors['news']:
            # TODO: add an icon if this piece of news was discussed in podcast
            text, links = split_news(item['text'])
            content += f"\n- {text}"
            for pos, link in enumerate(links):
                link_text = "link" + str(pos) if pos > 0 else ""
                content += f", [{link_text}]({link})"

    file_name = f'content/posts/{PUB_DTTM.strftime("%m%d%Y")}.ru.md'
    try:
        # trying to create a new file
        repo.create_file(file_name,
                         f'digest for {PUB_DTTM.strftime("%m%d%Y")}',
                         content,
                         branch=GITHUB_BRANCH)
    except Exception as e:
        # or update if exists
        prev_contents = repo.get_contents(file_name,
                                          ref=GITHUB_BRANCH)
        repo.update_file(prev_contents.path,
                         f'digest for {PUB_DTTM.strftime("%m%d%Y")}',
                         content,
                         prev_contents.sha,
                         branch=GITHUB_BRANCH)
    return {'response': f"File: {file_name}"}


def split_news(news_str):
    links = re.findall(r'(https?://[^\s]+)', news_str)
    text = news_str.strip()
    for link in links:
        text = text.replace(link, '')
    text = re.sub(' +', ' ', text).strip().replace('"', "'").capitalize()
    return (text, links)
