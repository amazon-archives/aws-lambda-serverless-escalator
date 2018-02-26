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
