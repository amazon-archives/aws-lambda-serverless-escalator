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
