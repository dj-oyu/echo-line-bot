import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as stepfunctions from 'aws-cdk-lib/aws-stepfunctions';
import * as stepfunctionsTasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as path from 'path';
import { Construct } from 'constructs';

/**
 * LINE Echo Bot Stack
 * 
 * This stack creates a serverless LINE bot with AI processing capabilities using:
 * - Lambda functions for webhook handling and AI processing
 * - DynamoDB for conversation state management
 * - Step Functions for orchestrating AI workflows
 * - API Gateway for receiving LINE webhook events
 */
export class LineEchoStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // DynamoDB table for conversation history with TTL for automatic cleanup
    const conversationTable = this.createConversationTable();

    // Reference existing secrets (created by GitHub Actions workflow)
    const secrets = this.createSecretReferences();

    // Lambda Layer for shared Python dependencies
    const dependenciesLayer = this.createDependenciesLayer();

    // Lambda Functions
    const lambdaFunctions = this.createLambdaFunctions(
      conversationTable,
      secrets,
      dependenciesLayer
    );

    // Grant DynamoDB permissions
    this.grantDynamoDBPermissions(conversationTable, lambdaFunctions);

    // Step Functions Workflow for AI processing
    const stateMachine = this.createStepFunctionsWorkflow(lambdaFunctions);

    // Configure webhook Lambda with Step Functions ARN
    lambdaFunctions.webhookLambda.addEnvironment('STEP_FUNCTION_ARN', stateMachine.stateMachineArn);
    stateMachine.grantStartExecution(lambdaFunctions.webhookLambda);

    // API Gateway for LINE webhook endpoint
    const api = new apigw.LambdaRestApi(this, 'Endpoint', { 
      handler: lambdaFunctions.webhookLambda,
      description: 'LINE Bot Webhook API',
      binaryMediaTypes: ['*/*'] // Support for various content types
    });

    // CloudFormation outputs
    new cdk.CfnOutput(this, 'ApiGatewayUrl', { 
      value: api.url,
      description: 'API Gateway URL for LINE webhook'
    });
    new cdk.CfnOutput(this, 'ConversationTableName', { 
      value: conversationTable.tableName,
      description: 'DynamoDB table name for conversation history'
    });
    new cdk.CfnOutput(this, 'StateMachineArn', { 
      value: stateMachine.stateMachineArn,
      description: 'Step Functions state machine ARN'
    });
  }

  /**
   * Creates DynamoDB table for conversation history with TTL
   */
  private createConversationTable(): dynamodb.Table {
    const tableName = 'line-bot-conversations';
    
    return new dynamodb.Table(this, 'ConversationHistory', {
      tableName: tableName,
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: 'ttl',
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN, // Retain table on stack deletion
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: false, // Disable to reduce costs
      },
    });
  }

  /**
   * Creates references to existing secrets in AWS Secrets Manager
   */
  private createSecretReferences() {
    return {
      lineChannelSecret: secretsmanager.Secret.fromSecretNameV2(this, 'LineChannelSecret', 'LINE_CHANNEL_SECRET'),
      lineChannelAccessToken: secretsmanager.Secret.fromSecretNameV2(this, 'LineChannelAccessToken', 'LINE_CHANNEL_ACCESS_TOKEN'),
      sambaNovaApiKey: secretsmanager.Secret.fromSecretNameV2(this, 'SambaNovaApiKey', 'SAMBA_NOVA_API_KEY'),
      xaiApiKeySecret: secretsmanager.Secret.fromSecretNameV2(this, 'XaiApiKeySecret', 'XAI_API_KEY'),
    };
  }

  /**
   * Creates Lambda layer for Python dependencies
   */
  private createDependenciesLayer(): lambda.LayerVersion {
    return new lambda.LayerVersion(this, 'DependenciesLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/layer-dist')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: 'Python dependencies for LINE bot Lambda functions',
    });
  }

  /**
   * Creates all Lambda functions for the LINE bot
   */
  private createLambdaFunctions(
    conversationTable: dynamodb.Table,
    secrets: ReturnType<typeof this.createSecretReferences>,
    dependenciesLayer: lambda.LayerVersion
  ) {
    const baseConfig = {
      runtime: lambda.Runtime.PYTHON_3_12,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      layers: [dependenciesLayer],
    };

    const webhookLambda = new lambda.Function(this, 'WebhookHandler', {
      ...baseConfig,
      handler: 'webhook_handler.lambda_handler',
      description: 'Handles LINE webhook events and initiates AI processing',
      environment: {
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
        CHANNEL_SECRET_NAME: secrets.lineChannelSecret.secretName,
        CHANNEL_ACCESS_TOKEN_NAME: secrets.lineChannelAccessToken.secretName,
        STEP_FUNCTION_ARN: '', // Placeholder, will be populated later
      },
    });
    secrets.lineChannelSecret.grantRead(webhookLambda);
    secrets.lineChannelAccessToken.grantRead(webhookLambda);

    const aiProcessorLambda = new lambda.Function(this, 'AiProcessor', {
      ...baseConfig,
      handler: 'ai_processor.lambda_handler',
      description: 'Processes user messages using SambaNova AI',
      timeout: cdk.Duration.seconds(60),
      environment: {
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
        SAMBA_NOVA_API_KEY_NAME: secrets.sambaNovaApiKey.secretName,
      },
    });
    secrets.sambaNovaApiKey.grantRead(aiProcessorLambda);

    const interimResponseSenderLambda = new lambda.Function(this, 'InterimResponseSender', {
      ...baseConfig,
      handler: 'interim_response_sender.lambda_handler',
      description: 'Sends interim response while processing complex queries',
      timeout: cdk.Duration.seconds(10),
      environment: {
        CHANNEL_ACCESS_TOKEN_NAME: secrets.lineChannelAccessToken.secretName,
      },
    });
    secrets.lineChannelAccessToken.grantRead(interimResponseSenderLambda);

    const grokProcessorLambda = new lambda.Function(this, 'GrokProcessor', {
      ...baseConfig,
      handler: 'grok_processor.lambda_handler',
      description: 'Processes queries using Grok AI for web search',
      timeout: cdk.Duration.seconds(180), // Longer timeout for potential long searches
      environment: {
        XAI_API_KEY_SECRET_NAME: secrets.xaiApiKeySecret.secretName,
      },
    });
    secrets.xaiApiKeySecret.grantRead(grokProcessorLambda);

    const responseSenderLambda = new lambda.Function(this, 'ResponseSender', {
      ...baseConfig,
      handler: 'response_sender.lambda_handler',
      description: 'Sends final response to LINE and saves conversation history',
      timeout: cdk.Duration.seconds(10),
      environment: {
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
        CHANNEL_ACCESS_TOKEN_NAME: secrets.lineChannelAccessToken.secretName,
      },
    });
    secrets.lineChannelAccessToken.grantRead(responseSenderLambda);

    return {
      webhookLambda,
      aiProcessorLambda,
      interimResponseSenderLambda,
      grokProcessorLambda,
      responseSenderLambda,
    };
  }

  /**
   * Grants DynamoDB permissions to relevant Lambda functions
   */
  private grantDynamoDBPermissions(
    conversationTable: dynamodb.Table,
    lambdaFunctions: ReturnType<typeof this.createLambdaFunctions>
  ): void {
    conversationTable.grantReadWriteData(lambdaFunctions.webhookLambda);
    conversationTable.grantReadWriteData(lambdaFunctions.aiProcessorLambda);
    conversationTable.grantReadWriteData(lambdaFunctions.responseSenderLambda);
  }

  /**
   * Creates Step Functions workflow for AI processing
   */
  private createStepFunctionsWorkflow(
    lambdaFunctions: ReturnType<typeof this.createLambdaFunctions>
  ): stepfunctions.StateMachine {
    const processAiTask = new stepfunctionsTasks.LambdaInvoke(this, 'ProcessWithSambaNova', {
      lambdaFunction: lambdaFunctions.aiProcessorLambda,
      resultPath: '$.aiProcessorResult',
      resultSelector: { 'Payload.$': '$.Payload' },
    });

    const sendInterimResponseTask = new stepfunctionsTasks.LambdaInvoke(this, 'SendInterimResponse', {
      lambdaFunction: lambdaFunctions.interimResponseSenderLambda,
      inputPath: '$.aiProcessorResult.Payload',
      resultPath: stepfunctions.JsonPath.DISCARD,
    });

    const processWithGrokTask = new stepfunctionsTasks.LambdaInvoke(this, 'ProcessWithGrok', {
      lambdaFunction: lambdaFunctions.grokProcessorLambda,
      inputPath: '$.aiProcessorResult.Payload',
      resultPath: '$.grokProcessorResult',
      resultSelector: { 'Payload.$': '$.Payload' },
    });

    const sendFinalResponseTask = new stepfunctionsTasks.LambdaInvoke(this, 'SendFinalResponse', {
      lambdaFunction: lambdaFunctions.responseSenderLambda,
      inputPath: '$.grokProcessorResult.Payload',
    });

    const sendDirectResponseTask = new stepfunctionsTasks.LambdaInvoke(this, 'SendDirectResponse', {
      lambdaFunction: lambdaFunctions.responseSenderLambda,
      inputPath: '$.aiProcessorResult.Payload',
    });

    const choice = new stepfunctions.Choice(this, 'CheckForToolCall')
      .when(
        stepfunctions.Condition.booleanEquals('$.aiProcessorResult.Payload.hasToolCall', true),
        sendInterimResponseTask.next(processWithGrokTask).next(sendFinalResponseTask)
      )
      .otherwise(sendDirectResponseTask);

    return new stepfunctions.StateMachine(this, 'AIProcessingWorkflow', {
      definitionBody: stepfunctions.DefinitionBody.fromChainable(processAiTask.next(choice)),
      timeout: cdk.Duration.minutes(5),
      comment: 'Orchestrates AI processing workflow with optional web search',
      stateMachineType: stepfunctions.StateMachineType.STANDARD,
    });
  }
}