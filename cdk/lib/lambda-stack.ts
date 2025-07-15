import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as stepfunctions from 'aws-cdk-lib/aws-stepfunctions';
import * as stepfunctionsTasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as path from 'path';
import { resolve } from 'path';

export class LineEchoStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // DynamoDB table
    const conversationTable = new dynamodb.Table(this, 'ConversationHistory', {
      tableName: 'line-bot-conversations',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: 'ttl',
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Secrets
    const lineChannelSecret = new secretsmanager.Secret(this, 'LineChannelSecret', { secretName: 'LINE_CHANNEL_SECRET' });
    const lineChannelAccessToken = new secretsmanager.Secret(this, 'LineChannelAccessToken', { secretName: 'LINE_CHANNEL_ACCESS_TOKEN' });
    const sambaNovaApiKey = new secretsmanager.Secret(this, 'SambaNovaApiKey', { secretName: 'SAMBA_NOVA_API_KEY' });
    const xaiApiKeySecret = new secretsmanager.Secret(this, 'XaiApiKeySecret', { secretName: 'XAI_API_KEY' });

    // Lambda Layer for shared Python dependencies
    const dependenciesLayer = new lambda.LayerVersion(this, 'DependenciesLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/layer-dist')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: 'Python dependencies for LINE bot Lambda functions',
    });

    // Lambda Functions
    const webhookLambda = new lambda.Function(this, 'WebhookHandler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'webhook_handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      layers: [dependenciesLayer],
      environment: {
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
        CHANNEL_SECRET_NAME: lineChannelSecret.secretName,
        STEP_FUNCTION_ARN: '', // Placeholder, will be populated later
      },
    });
    lineChannelSecret.grantRead(webhookLambda);

    const aiProcessorLambda = new lambda.Function(this, 'AiProcessor', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'ai_processor.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      layers: [dependenciesLayer],
      timeout: cdk.Duration.seconds(15),
      environment: {
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
        SAMBA_NOVA_API_KEY_NAME: sambaNovaApiKey.secretName,
      },
    });
    sambaNovaApiKey.grantRead(aiProcessorLambda);

    const interimResponseSenderLambda = new lambda.Function(this, 'InterimResponseSender', {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: 'interim_response_sender.lambda_handler',
        code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
        layers: [dependenciesLayer],
          timeout: cdk.Duration.seconds(10),
        environment: {
            CHANNEL_ACCESS_TOKEN_NAME: lineChannelAccessToken.secretName,
        },
    });
    lineChannelAccessToken.grantRead(interimResponseSenderLambda);

    const grokProcessorLambda = new lambda.Function(this, 'GrokProcessor', {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: 'grok_processor.lambda_handler',
        code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
        layers: [dependenciesLayer],
          timeout: cdk.Duration.seconds(60), // Longer timeout for potential long searches
        environment: {
            XAI_API_KEY_SECRET_NAME: xaiApiKeySecret.secretName,
        },
    });
    xaiApiKeySecret.grantRead(grokProcessorLambda);

    const responseSenderLambda = new lambda.Function(this, 'ResponseSender', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'response_sender.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      layers: [dependenciesLayer],
      timeout: cdk.Duration.seconds(10),
      environment: {
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
        CHANNEL_ACCESS_TOKEN_NAME: lineChannelAccessToken.secretName,
      },
    });
    lineChannelAccessToken.grantRead(responseSenderLambda);

    // Grant DynamoDB permissions
    conversationTable.grantReadWriteData(webhookLambda);
    conversationTable.grantReadWriteData(aiProcessorLambda);
    conversationTable.grantReadWriteData(responseSenderLambda);

    // Step Functions Workflow Definition
    const processAiTask = new stepfunctionsTasks.LambdaInvoke(this, 'ProcessWithSambaNova', {
        lambdaFunction: aiProcessorLambda,
        resultPath: '$.aiProcessorResult',
        resultSelector: { 'Payload.$': '$.Payload' },
    });

    const sendInterimResponseTask = new stepfunctionsTasks.LambdaInvoke(this, 'SendInterimResponse', {
        lambdaFunction: interimResponseSenderLambda,
        inputPath: '$.aiProcessorResult.Payload',
        resultPath: '$.interimResponseResult',
    });

    const processWithGrokTask = new stepfunctionsTasks.LambdaInvoke(this, 'ProcessWithGrok', {
        lambdaFunction: grokProcessorLambda,
        inputPath: '$.aiProcessorResult.Payload',
        resultPath: '$.grokProcessorResult',
        resultSelector: { 'Payload.$': '$.Payload' },
    });

    const sendFinalResponseTask = new stepfunctionsTasks.LambdaInvoke(this, 'SendFinalResponse', {
        lambdaFunction: responseSenderLambda,
        inputPath: '$.grokProcessorResult.Payload',
    });

    const sendDirectResponseTask = new stepfunctionsTasks.LambdaInvoke(this, 'SendDirectResponse', {
        lambdaFunction: responseSenderLambda,
        inputPath: '$.aiProcessorResult.Payload',
    });

    const choice = new stepfunctions.Choice(this, 'CheckForToolCall')
        .when(
            stepfunctions.Condition.booleanEquals('$.aiProcessorResult.Payload.hasToolCall', true),
            sendInterimResponseTask.next(processWithGrokTask).next(sendFinalResponseTask)
        )
        .otherwise(sendDirectResponseTask);

    const stateMachine = new stepfunctions.StateMachine(this, 'AIProcessingWorkflow', {
      definitionBody: stepfunctions.DefinitionBody.fromChainable(processAiTask.next(choice)),
      timeout: cdk.Duration.minutes(5),
    });

    // Grant webhook permissions
    webhookLambda.addEnvironment('STEP_FUNCTION_ARN', stateMachine.stateMachineArn);
    stateMachine.grantStartExecution(webhookLambda);

    // API Gateway
    const api = new apigw.LambdaRestApi(this, 'Endpoint', { handler: webhookLambda });

    new cdk.CfnOutput(this, 'ApiGatewayUrl', { value: api.url });
  }
}