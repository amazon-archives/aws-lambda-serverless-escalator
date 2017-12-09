# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the "License"). You may not use this file except in
# compliance with the License. A copy of the License is located at
#
#     http://aws.amazon.com/asl/
#
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific
# language governing permissions and limitations under the License.

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
