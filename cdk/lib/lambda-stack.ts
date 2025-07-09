import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as stepfunctions from 'aws-cdk-lib/aws-stepfunctions';
import * as stepfunctionsTasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as path from 'path';
import * as dotenv from 'dotenv';
import { randomUUID } from 'crypto';
import { resolve } from 'path';

// 環境変数の読み込み
dotenv.config({ path: path.join(__dirname, '../../.env.local') });

export class LineEchoStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // DynamoDB table for conversation history
    const conversationTable = new dynamodb.Table(this, 'ConversationHistory', {
      tableName: 'line-bot-conversations',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'conversationId', type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: 'ttl',
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Line bot layer
   const lineBotLayer = new lambda.LayerVersion(this, 'LineBotLayer', {
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Layer for line-bot-sdk and openai',
      code: lambda.Code.fromAsset(resolve(__dirname), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            [
              'mkdir -p /asset-output/python',
              'pip install line-bot-sdk openai boto3 pytz -t /asset-output/python',
            ].join(' && ')
          ]
        }
      })
    });

    // Webhook handler Lambda (fast response)
    const webhookLambda = new lambda.Function(this, 'webhookHandler', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'webhook_handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      layers: [lineBotLayer],
      timeout: cdk.Duration.seconds(10),
      environment: {
        CHANNEL_SECRET: process.env.CHANNEL_SECRET || '',
        CHANNEL_ACCESS_TOKEN: process.env.CHANNEL_ACCESS_TOKEN || '',
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
      },
    });

    // AI processing Lambda (for Step Functions)
    const aiProcessorLambda = new lambda.Function(this, 'aiProcessor', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'ai_processor.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      layers: [lineBotLayer],
      timeout: cdk.Duration.seconds(60),
      environment: {
        CHANNEL_ACCESS_TOKEN: process.env.CHANNEL_ACCESS_TOKEN || '',
        SAMBA_NOVA_API_KEY: process.env.SAMBA_NOVA_API_KEY || '',
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
      },
    });

    // Response sender Lambda
    const responseSenderLambda = new lambda.Function(this, 'responseSender', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'response_sender.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      layers: [lineBotLayer],
      timeout: cdk.Duration.seconds(10),
      environment: {
        CHANNEL_ACCESS_TOKEN: process.env.CHANNEL_ACCESS_TOKEN || '',
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
      },
    });

    // Grant DynamoDB permissions
    conversationTable.grantReadWriteData(webhookLambda);
    conversationTable.grantReadWriteData(aiProcessorLambda);
    conversationTable.grantReadWriteData(responseSenderLambda);

    // Step Functions workflow
    const aiProcessingTask = new stepfunctionsTasks.LambdaInvoke(this, 'ProcessAI', {
      lambdaFunction: aiProcessorLambda,
      outputPath: '$.Payload',
    });

    const sendResponseTask = new stepfunctionsTasks.LambdaInvoke(this, 'SendResponse', {
      lambdaFunction: responseSenderLambda,
      outputPath: '$.Payload',
    });

    const aiWorkflow = aiProcessingTask.next(sendResponseTask);

    const stateMachine = new stepfunctions.StateMachine(this, 'AIProcessingWorkflow', {
      definitionBody: stepfunctions.DefinitionBody.fromChainable(aiWorkflow),
      timeout: cdk.Duration.minutes(5),
    });

    // Grant webhook Lambda permission to start Step Functions
    webhookLambda.addToRolePolicy(new iam.PolicyStatement({
      actions: ['states:StartExecution'],
      resources: [stateMachine.stateMachineArn],
    }));

    // Add Step Functions ARN to webhook Lambda environment
    webhookLambda.addEnvironment('STEP_FUNCTION_ARN', stateMachine.stateMachineArn);

    const api = new apigw.LambdaRestApi(this, 'Endpoint', {
      handler: webhookLambda,
    });

    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: api.url,
      description: 'API Gateway URL for the Line Echo Bot',
    });
  }
}
