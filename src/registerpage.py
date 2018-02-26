# Copyright 2017-2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import sys
import boto3
import json
import datetime
import hashlib
import logging

debug = os.environ.get('DEBUG', None) is not None
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG if debug else logging.ERROR)

# Global to improve load times
dynamodb = boto3.resource('dynamodb')
pages = dynamodb.Table(os.environ['DDB_PAGES_TABLE'])
teams = dynamodb.Table(os.environ['DDB_TEAMS_TABLE'])

def registerpage(sender, email, subject, body, messageId):
    response = teams.get_item(Key={'email': email},
        ReturnConsumedCapacity='NONE')
    try:
        team = response['Item']
    except KeyError as e:
        logger.error("no such team {}".format(email))
        logger.debug("Exception: %s", e, exc_info=True)
        raise KeyError("no such team {}".format(email))
        sys.exit(100)

    page = {
        'timestamp': int(datetime.datetime.timestamp(datetime.datetime.now())),
        'team': team['email'],
        'ack': False,
        'ttl': int(datetime.datetime.timestamp(datetime.datetime.now() + datetime.timedelta(days=7))),
        'stage': -1
    }

    checksum = hashlib.sha256()
    checksum.update(bytes((page['team'] + subject + messageId + body)[0:4096], 'utf-8'))
    page['id'] = checksum.hexdigest()

    page['subject'] = subject
    page['body'] = "Ack page: {0}/{1}\n\n".format(os.environ['ACK_API_URL'], page['id']) \
    + "From: {}\n\n".format(sender) \
    + body

    # Step Function invocation can fail quietly on ConditionalCheckFailedException due to duplicate page
    pages.put_item(Item=page,
        ConditionExpression=boto3.dynamodb.conditions.Attr('id').not_exists())
    return page, team

def handler(event, context):
    """event = {
        'from': sender,
        'email': recipient,
        'subject': subject,
        'body': body,
        'messageId': messageId
    }"""
    page, team = registerpage(event['from'], event['email'], event['subject'], event['body'],
                            event.get('messageId', context.aws_request_id))
    return {'page': page, 'team': team}
