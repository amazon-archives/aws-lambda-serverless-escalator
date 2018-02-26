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
import operator
import itertools
import logging

debug = os.environ.get('DEBUG', None) is not None
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG if debug else logging.ERROR)

# Global to improve load times
dynamodb = boto3.resource('dynamodb')
pages = dynamodb.Table(os.environ['DDB_PAGES_TABLE'])
ses = boto3.client('ses')

def grouper(n, iterable):
    args = [iter(iterable)] * n
    return itertools.zip_longest(fillvalue=None,*args)

def sendpage(page, team):
    stages = sorted(team['stages'], key=operator.itemgetter('order'))

    topage = []
    for stage in stages:
        """iterate through stages in order until you see the first stage that hasn't been paged.
        Add each list of emails to the to list of recipients. Set newstage and delay in case
        last stage is reached to repeatedly page the last stage on a delay."""
        topage.extend(stage['email'])
        newstage = stage['order']
        delay = stage['delay']
        if stage['order'] > page['stage']:
            break

    sent = []
    for to in grouper(50, topage):
        response = ses.send_email(
            Source="no-reply@{}".format(os.environ.get('SES_DOMAIN',
                page['team'].split('@')[1])),
            Destination={'ToAddresses': [addr for addr in to if addr is not None]},
            Message={
                'Subject': {'Data': page['subject']},
                'Body': {'Text': {'Data': page['body']}}
            })
        sent.append(response['MessageId'])

    response = pages.update_item(Key={'id': page['id']},
        UpdateExpression='SET stage = :order',
        ExpressionAttributeValues={
            ':order': int(newstage)
        })

    return sent, delay

def handler(event, context):
    """event = {
        'page': page object,
        'team': team object
    }"""

    sent, delay = sendpage(event['page'], event['team'])

    event['sent'] = sent
    event['waitseconds'] = int(delay)
    return event
