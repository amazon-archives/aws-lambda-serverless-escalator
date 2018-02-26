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

"""Find just the text body, discard the html and attachments"""

import email.parser
import email.policy
import os
import logging
import json
import boto3

debug = os.environ.get('DEBUG', None) is not None
logger = logging.getLogger()
logger.setLevel(logging.DEBUG if debug else logging.INFO)

# Global to improve load times
s3 = boto3.client('s3')
sfn = boto3.client('stepfunctions')

def get_body(m):
    """extract the plain text body. return the body"""
    if m.is_multipart():
        body = m.get_body(preferencelist=('plain',)).get_payload(decode=True)
    else:
        body = m.get_payload(decode=True)
    if isinstance(body, bytes):
        return body.decode()
    else:
        return body

def incomingemail(mail, receipt):
    response = s3.get_object(Bucket=os.environ['BODY_BUCKET'],
        Key=os.path.join(os.environ.get('BODY_PREFIX',''),
            mail['messageId']))

    m = email.parser.BytesParser(policy=email.policy.default).parsebytes(response['Body'].read())
    output = {
        'from': mail['commonHeaders']['from'][0],
        'messageId': mail['messageId'],
        'subject': mail['commonHeaders']['subject'],
        'body': get_body(m)
    }

    for recipient in receipt['recipients']:
        output['email'] = recipient
        logger.info(json.dumps(output))
        response = sfn.start_execution(stateMachineArn=os.environ['SFN_ARN'],
            name=recipient+output['messageId'],
            input=json.dumps(output))

def handler(event, context):
    incomingemail(event['Records'][0]['ses']['mail'], event['Records'][0]['ses']['receipt'])
