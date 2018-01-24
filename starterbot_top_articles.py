#!/usr/bin/python
from __future__ import print_function  # Python 2/3 compatibility
import os
import time
import re
from slackclient import SlackClient
from datetime import datetime

import boto3
import json
import decimal
from boto3.dynamodb.conditions import Key, Attr
from pprint import pprint
import time
from datetime import datetime
import urllib

# DYNAMODB CODE

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('time_aggregate_page_views')
# now = (int(time.time()))
# nowint = int(now//60 * 60)
# times = list(range(nowint, nowint-300, -60))


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

# viewcount = {}
# for t in times:
#     query_results = table.query(KeyConditionExpression=Key('event_time_epoch').eq(t))
#     for q in query_results['Items']:
#         article_url = (q['thing_id'])
#         views = (int(q['view_count']))
#         viewcount[article_url] = viewcount.get(article_url, 0) + views
#
# top_views = sorted(viewcount.items(), key=lambda x: x[1], reverse=True)[:5]

# FT API
# Connecting to FT API
api_url_base ='http://api.ft.com/content/'
api_token = (os.environ.get('FT_API_TOKEN'))

def get_article_info(thing_id):
    url = '{}{}?apiKey={}'.format(api_url_base, thing_id, api_token)
    # print (url)
    with urllib.request.urlopen(url) as response:
        html = json.loads(response.read())
        return html

# top_article_details = []
#
# for t in top_views:
#     article = get_article_info(t[0])
#     views_per_article = (t[1])
#     f = [article['title'], article['webUrl'], views_per_article]
#     top_article_details.append(f)

# SLACKBOT
# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 0.5 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "top article"
MENTION_REGEX = "^<@(|[WU].+)>(.*)"


def current_5_min_window(now):
    nowint = int(now//60 * 60)
    times = list(range(nowint-300, nowint, 60))
    return times


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            message = event["text"]
            # user_id, message = parse_direct_mention(event["text"])
            # if user_id == starterbot_id:
            return message, event["channel"]
    return None, None

# def parse_direct_mention(message_text):
#     """
#         Finds a direct mention (a mention that is at the beginning) in message text
#         and returns the user ID which was mentioned. If there is no direct mention, returns None
#     """
#     matches = re.search(MENTION_REGEX, message_text)
#     # the first group contains the username, the second group contains the remaining message
#     return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try asking me for top *{}s*.".format(EXAMPLE_COMMAND)

    # Finds and executes the given command, filling in response
    response = None
    # This is where you start to implement more commands!
    # if command.startswith(EXAMPLE_COMMAND):
    if command.lower().find(EXAMPLE_COMMAND) != -1:

        times = current_5_min_window(int(time.time()))

        viewcount = {}
        for t in times:
            query_results = table.query(KeyConditionExpression=Key('event_time_epoch').eq(t))
            for q in query_results['Items']:
                article_url = (q['thing_id'])
                views = (int(q['view_count']))
                viewcount[article_url] = viewcount.get(article_url, 0) + views

        top_views = sorted(viewcount.items(), key=lambda x: x[1], reverse=True)[:5]

        top_article_details = []

        for t in top_views:
            article = get_article_info(t[0])
            views_per_article = (t[1])
            f = [article['title'], article['webUrl'], views_per_article]
            top_article_details.append(f)

        response = "Sure! It is *{}*, in the last 5 minutes, the top {} articles with the highest number of views are:" \
                   "\n".format(datetime.now().strftime('%H:%M:%S'), str(5))
        slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=response)

        for a in top_article_details:
            slack_client.api_call(
                "chat.postMessage",
                channel=channel,
                attachments=[
                    {
                        "color": "#36a64f",
                        "title": str(a[0]),
                        "title_link": str(a[1]),
                        "text": "viewcount: " + str(a[2])
                    }
                ]
            )
    else:
        slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=default_response)

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # slack_client.rtm_send_message(CHANNEL_NAME, "I'm ALIVE!!!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")