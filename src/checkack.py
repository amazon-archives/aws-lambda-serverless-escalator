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
import json
import boto3
import logging

debug = os.environ.get('DEBUG', None) is not None
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG if debug else logging.ERROR)

# Global to improve load times
dynamodb = boto3.resource('dynamodb')
pages = dynamodb.Table(os.environ['DDB_PAGES_TABLE'])

def checkack(pageid):
    response = pages.get_item(Key={'id': pageid},
        ConsistentRead=True,
        ReturnConsumedCapacity='NONE')
    try:
        page = response['Item']
    except KeyError as e:
        logger.error("no such page {}".format(pageid))
        logger.debug("Exception: %s", e, exc_info=True)
        raise KeyError("no such page {}".format(pageid))
        sys.exit(100)

    return page.get('ack', False)

def handler(event, context):
    """event = {
            'page': page object,
            'team': team object
        }"""
    event['ack'] = checkack(event['page']['id'])
    return event
