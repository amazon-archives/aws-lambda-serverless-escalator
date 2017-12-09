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
