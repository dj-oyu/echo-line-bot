import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as stepfunctions from 'aws-cdk-lib/aws-stepfunctions';
import * as stepfunctionsTasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as path from 'path';
import { Construct } from 'constructs';

const PYTHON_RUNTIME = lambda.Runtime.PYTHON_3_14;

/**
 * Paths excluded from the Lambda function asset.
 *
 * `layer-dist` holds the dependency layer's contents, which are already
 * mounted at /opt/python by the layer itself. Bundling them into every
 * function package too made each package 33 MB instead of ~50 KB, slowing
 * cold starts and eating into the 250 MB unzipped function+layers limit.
 * Excluding tests and caches also keeps the asset hash stable across machines.
 */
const FUNCTION_ASSET_EXCLUDES = ['layer-dist', 'tests', '**/__pycache__'];

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
      groqApiKeySecret: secretsmanager.Secret.fromSecretNameV2(this, 'GroqApiKeySecret', 'GROQ_API_KEY'),
      xaiApiKeySecret: secretsmanager.Secret.fromSecretNameV2(this, 'XaiApiKeySecret', 'XAI_API_KEY'),
    };
  }

  /**
   * Creates Lambda layer for Python dependencies
   */
  private createDependenciesLayer(): lambda.LayerVersion {
    return new lambda.LayerVersion(this, 'DependenciesLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/layer-dist')),
      compatibleRuntimes: [PYTHON_RUNTIME],
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
    // 128 MB stopped being enough once delivery moved into the producing
    // stages: ai_processor now loads linebot (320 pydantic modules) on top of
    // openai, and grok_processor on top of xai_sdk and grpc. Production hit
    // "Max Memory Used: 128 MB" and then hung until the 60 s timeout — the
    // Groq call had already returned, so the answer was lost after being paid
    // for. Lambda scales CPU with memory, so this also shortens the imports
    // that made the ceiling expensive to sit against.
    const baseConfig = {
      memorySize: 512,
      runtime: PYTHON_RUNTIME,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda'), {
        exclude: FUNCTION_ASSET_EXCLUDES,
      }),
      layers: [dependenciesLayer],
    };

    const webhookLambda = new lambda.Function(this, 'WebhookHandler', {
      ...baseConfig,
      handler: 'webhook_handler.lambda_handler',
      description: 'Handles LINE webhook events and initiates AI processing',
      // The CDK default is 3 s, but cold start init alone measured 2.8-3.2 s,
      // so cold invocations were being killed before they could start the
      // Step Function and LINE got no response. Warm invocations take ~0.6 s;
      // this ceiling only exists to survive a cold start.
      timeout: cdk.Duration.seconds(10),
      environment: {
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
        CHANNEL_SECRET_NAME: secrets.lineChannelSecret.secretName,
        CHANNEL_ACCESS_TOKEN_NAME: secrets.lineChannelAccessToken.secretName,
        STEP_FUNCTION_ARN: '', // Placeholder, will be populated later
        // Read only when /forget triggers the lazy ai_processor import
        SAMBA_NOVA_API_KEY_NAME: secrets.sambaNovaApiKey.secretName,
        GROQ_API_KEY_NAME: secrets.groqApiKeySecret.secretName,
      },
    });
    secrets.lineChannelSecret.grantRead(webhookLambda);
    secrets.lineChannelAccessToken.grantRead(webhookLambda);

    const aiProcessorLambda = new lambda.Function(this, 'AiProcessor', {
      ...baseConfig,
      handler: 'ai_processor.lambda_handler',
      description: 'Routes a message: answers directly or requests a web search',
      timeout: cdk.Duration.seconds(60),
      environment: {
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
        SAMBA_NOVA_API_KEY_NAME: secrets.sambaNovaApiKey.secretName,
        GROQ_API_KEY_NAME: secrets.groqApiKeySecret.secretName,
        // Used only when a tool call fires, to tell the user a search started
        CHANNEL_ACCESS_TOKEN_NAME: secrets.lineChannelAccessToken.secretName,
        AI_BACKEND: process.env.AI_BACKEND || 'groq',
        SAMBANOVA_MODEL: process.env.SAMBANOVA_MODEL || 'DeepSeek-V3.2',
        GROQ_MODEL: process.env.GROQ_MODEL || 'openai/gpt-oss-20b',
        // Only forwarded when explicitly set: otherwise ai_processor derives a
        // value the configured model accepts (the vocabularies are disjoint).
        ...(process.env.GROQ_REASONING_EFFORT
          ? { GROQ_REASONING_EFFORT: process.env.GROQ_REASONING_EFFORT }
          : {}),
      },
    });
    secrets.sambaNovaApiKey.grantRead(aiProcessorLambda);
    secrets.groqApiKeySecret.grantRead(aiProcessorLambda);
    secrets.lineChannelAccessToken.grantRead(aiProcessorLambda);

    const grokProcessorLambda = new lambda.Function(this, 'GrokProcessor', {
      ...baseConfig,
      handler: 'grok_processor.lambda_handler',
      description: 'Processes queries using Grok AI for web search',
      timeout: cdk.Duration.seconds(180), // Longer timeout for potential long searches
      environment: {
        XAI_API_KEY_SECRET_NAME: secrets.xaiApiKeySecret.secretName,
        XAI_MODEL: process.env.XAI_MODEL || 'grok-4.6',
        // This stage now delivers the answer and records it
        CHANNEL_ACCESS_TOKEN_NAME: secrets.lineChannelAccessToken.secretName,
        CONVERSATION_TABLE_NAME: conversationTable.tableName,
      },
    });
    secrets.xaiApiKeySecret.grantRead(grokProcessorLambda);
    secrets.lineChannelAccessToken.grantRead(grokProcessorLambda);

    const responseSenderLambda = new lambda.Function(this, 'ResponseSender', {
      ...baseConfig,
      handler: 'response_sender.lambda_handler',
      description: 'Notifies the user when a stage failed before it could reply',
      // It timed out at 10 s doing exactly this: cold start, linebot import,
      // secret fetch, push. The safety net must not be the thing that fails.
      timeout: cdk.Duration.seconds(30),
      environment: {
        CHANNEL_ACCESS_TOKEN_NAME: secrets.lineChannelAccessToken.secretName,
      },
    });
    secrets.lineChannelAccessToken.grantRead(responseSenderLambda);

    return {
      webhookLambda,
      aiProcessorLambda,
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
    conversationTable.grantReadWriteData(lambdaFunctions.grokProcessorLambda);
  }

  /**
   * Creates Step Functions workflow for AI processing
   */
  private createStepFunctionsWorkflow(
    lambdaFunctions: ReturnType<typeof this.createLambdaFunctions>
  ): stepfunctions.StateMachine {
    const processAiTask = new stepfunctionsTasks.LambdaInvoke(this, 'ProcessWithLLM', {
      lambdaFunction: lambdaFunctions.aiProcessorLambda,
      resultPath: '$.aiProcessorResult',
      resultSelector: { 'Payload.$': '$.Payload' },
    });

    // Reached only through a Catch: the stage that owed the user a reply died
    // before sending one. Its cold start lands on the failure path only.
    const notifyFailureTask = new stepfunctionsTasks.LambdaInvoke(this, 'NotifyFailure', {
      lambdaFunction: lambdaFunctions.responseSenderLambda,
    });

    processAiTask.addCatch(notifyFailureTask, { resultPath: '$.error' });

    const processWithGrokTask = new stepfunctionsTasks.LambdaInvoke(this, 'ProcessWithGrok', {
      lambdaFunction: lambdaFunctions.grokProcessorLambda,
      inputPath: '$.aiProcessorResult.Payload',
      resultPath: '$.grokProcessorResult',
      resultSelector: { 'Payload.$': '$.Payload' },
    });
    processWithGrokTask.addCatch(notifyFailureTask, { resultPath: '$.error' });

    // The Choice stays: it is what keeps an ordinary message out of a ~60 s web
    // search. It costs nothing — the measured transition is 0.00 s.
    // Each branch ends at the stage that delivers the message.
    const choice = new stepfunctions.Choice(this, 'CheckForToolCall')
      .when(
        stepfunctions.Condition.booleanEquals('$.aiProcessorResult.Payload.hasToolCall', true),
        processWithGrokTask
      )
      .otherwise(new stepfunctions.Succeed(this, 'AnsweredDirectly'));

    return new stepfunctions.StateMachine(this, 'AIProcessingWorkflow', {
      definitionBody: stepfunctions.DefinitionBody.fromChainable(processAiTask.next(choice)),
      timeout: cdk.Duration.minutes(5),
      comment: 'Orchestrates AI processing workflow with optional web search',
      stateMachineType: stepfunctions.StateMachineType.STANDARD,
    });
  }
}