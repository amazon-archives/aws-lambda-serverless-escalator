serverless-escalator is a page escalation tool using [AWS SAM](https://github.com/awslabs/serverless-application-model)

# Usage
## Send a Page
You can send a page to serverless-escalator via email or API. For email, simply send a plain text email to the team email address(other parts will be stripped e.g. html and images).

NOTE: The only information needed to send a page is the team email address. The body and subject are stored unencrypted in your account, so this should only be used with non-sensitive data.

The API endpoint includes an unauthenticated `page` POST action. The body is a JSON object with the following schema:
```
{
    "from": "sender email address",
    "email": "team email address",
    "subject": "page subject",
    "body": "page body"
}
```

## Create a team
The API endpoint includes a `registerteam` POST action that can be accessed with IAM authentication.
The body is a JSON object following the [teams table schema](#teams).

``` team.json
{
  "email": "testteam@SESDomain",
  "stages": [
    {
      "delay": 600,
      "email": [
        "tier1@example.com"
      ],
      "order": 10
    },
    {
      "delay": 600,
      "email": [
        "tier2@example.com"
      ],
      "order": 20
    }
  ]
}
```

Using [awscurl](https://github.com/okigan/awscurl), you can send signed requests to create teams.
```
$ awscurl --profile myawscliprofile https://$DOMAIN/registerteam -X POST -d @/tmp/team.json
```

# Setup
Set up or make sure you have the following available.

## Route53 Zone

Set up a public hosted zone in Route53. This domain will be used for SES sending and receiving and
API Gateway. The Hosted Zone ID will be used as input for the CloudFormation Stack.

```
$ aws route53 create-hosted-zone --name fqdn.example.com --caller-reference `date +%s`
{
    "HostedZone": {
        "Id": "/hostedzone/ZZZZZZZZZZZZZZ",
        "Name": "fqdn.example.com.",
        "ResourceRecordSetCount": 2,
        "CallerReference": "1511368437",
        "Config": {
            "PrivateZone": false
        }
    },
    "ChangeInfo": {
        "Id": "/change/CAMZCCCCCCCCC",
        "SubmittedAt": "2017-11-22T16:33:56.185Z",
        "Status": "PENDING"
    },
    "DelegationSet": {
        "NameServers": [
            "ns-nnn.awsdns-15.net",
            "ns-nnnn.awsdns-60.co.uk",
            "ns-nnn.awsdns-53.com",
            "ns-nnnn.awsdns-00.org"
        ]
    },
    "Location": "https://route53.amazonaws.com/2013-04-01/hostedzone/ZZZZZZZZZZZZZZ"
}
```

## ACM Certificate
Until CloudFormation supports regional endpoints for API Gateway, you will need to create your
certificates in us-east-1. The ARN will be used as input for the CloudFormation Stack.

Use the Route53 Console to [create a certificate using DNS
validation](http://docs.aws.amazon.com/acm/latest/userguide/gs-acm-validate-dns.html). Be sure that
you are in the us-east-1 region.

## Artifact Bucket
The AWS SAM needs an S3 bucket to store artifacts such as Lambda functions and Swagger files. Create
a bucket in the region you choose to run in.

`aws s3api create-bucket --bucket artifactbucket`

## Deploy CloudFormation Stack
The CloudFormation Stack uses the [AWS Serverless Application
Model](https://github.com/awslabs/serverless-application-model).

`$BUCKET` below is the artifact bucket created in the previous step.

Stack Parameters:
    Domain: Domain for the API endpoint
    DomainCertArn: ACM certificate ARN for Domain in us-east-1
    Env: API deployment stage name
    SESDomain: Domain for sending email
    EscalatorAPIURI: S3 URI for escalator api swagger
    Route53Zone: Route53 hosted zone ID

```
$ aws cloudformation package --template-file escalator-sam.yaml --s3-bucket $BUCKET \
    --s3-prefix escalator --output-template-file escalator-packaged.yaml
$ aws s3 cp escalatorapi.yaml s3://$BUCKET/escalator/escalatorapi.yaml
$ aws cloudformation deploy --template-file escalator-packaged.yaml \
    --stack-name serverless-escalator \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides Domain=$DOMAIN Env=Prod SESDomain=$DOMAIN \
    EscalatorAPIURI=s3://$BUCKET/escalator/escalatorapi.yaml \
    Route53Zone=$ROUTE53ZONEID DomainCertArn=$CERTIFICATEARN
```

## SES Receive Ruleset
SES Receiving rules can't be managed by CloudFormation. The outputs of the stack contain the
`IncomingEmailARN` and `EscalatorBucket` values needed for the rules. Replace the placeholders in
`SES/savebody.json` and `SES/startsfn.json`. The rules will apply to all addresses in `SESDomain`.

```
$ aws ses create-receipt-rule-set --rule-set-name serverless-escalator
$ aws ses create-receipt-rule --rule-set-name serverless-escalator --rule file://SES/savebody.json
$ aws ses create-receipt-rule --rule-set-name --after savebody --rule file://SES/startsfn.json
```

# Components
![architecture diagram](docs/Escalator.png)

## incoming_email
Lambda function triggered by SES

1. invoke step function

## registerpage
Lambda function triggered by Step Functions

1. Lookup team by email in DynamoDB `teams` table
2. Register page in DynamoDB `pages` table
3. Append ack URL to email body
4. Call `sendpage`

## checkack
Lambda function invoked by step functions

1. check if the page was acked before proceeding to the send page state or finishing

## sendpage
Lambda function invoked by step functions

1. Send email to appropriate stages
2. Schedule next invocation of `sendpage` according to next stage's delay

## pages
DynamoDB table to track pages

Schema:
```
{
    id: page id,
    timestamp: creation time,
    ack: False or timestamp of ack
    team: email of team in `teams` table,
    stage: `order` of last stage called    
}
```

## teams
DynamoDB to configure teams

Schema:
```
{
    email: email that pages get sent to,
    stages: [
        {
            order: integer with priority for stage. lower numbers are paged first,
            email: [email addresses to send pages for stage],
            delay: seconds to wait before sending to the next stage
        }
    ]
}
```
