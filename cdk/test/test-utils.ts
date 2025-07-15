import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { LineEchoStack } from '../lib/lambda-stack';

/**
 * Test Utilities for LINE Echo Stack
 * 
 * This module provides utilities for testing following t_wada's principles:
 * - Reusable test components
 * - Consistent test setup
 * - Test data management
 * - Testing best practices
 */

export interface TestStackProps {
  stackName?: string;
  description?: string;
  environment?: Record<string, string>;
}

export class TestStackBuilder {
  private app: cdk.App;
  private props: TestStackProps;

  constructor(props: TestStackProps = {}) {
    this.app = new cdk.App();
    this.props = {
      stackName: 'TestStack',
      description: 'LINE Echo Bot Test Stack',
      ...props
    };
  }

  public build(): { stack: LineEchoStack; template: Template } {
    const stack = new LineEchoStack(this.app, this.props.stackName!, {
      description: this.props.description
    });
    
    const template = Template.fromStack(stack);
    return { stack, template };
  }

  public withCustomEnvironment(env: Record<string, string>): TestStackBuilder {
    this.props.environment = { ...this.props.environment, ...env };
    return this;
  }

  public withDescription(description: string): TestStackBuilder {
    this.props.description = description;
    return this;
  }
}

export class TestDataFactory {
  /**
   * Creates standardized test data for Lambda function validation
   */
  public static createLambdaTestData() {
    return {
      expectedFunctions: [
        {
          handler: 'webhook_handler.lambda_handler',
          runtime: 'python3.12',
          description: 'Handles LINE webhook events and initiates AI processing',
          timeout: 3, // Default timeout
          requiresConversationTable: true,
          requiresLineCredentials: true,
          requiresStepFunctionsArn: true
        },
        {
          handler: 'ai_processor.lambda_handler',
          runtime: 'python3.12',
          description: 'Processes user messages using SambaNova AI',
          timeout: 15,
          requiresConversationTable: true,
          requiresSambaNovaCredentials: true
        },
        {
          handler: 'interim_response_sender.lambda_handler',
          runtime: 'python3.12',
          description: 'Sends interim response while processing complex queries',
          timeout: 10,
          requiresLineCredentials: true
        },
        {
          handler: 'grok_processor.lambda_handler',
          runtime: 'python3.12',
          description: 'Processes queries using Grok AI for web search',
          timeout: 180,
          requiresXaiCredentials: true
        },
        {
          handler: 'response_sender.lambda_handler',
          runtime: 'python3.12',
          description: 'Sends final response to LINE and saves conversation history',
          timeout: 10,
          requiresConversationTable: true,
          requiresLineCredentials: true
        }
      ]
    };
  }

  /**
   * Creates standardized test data for DynamoDB validation
   */
  public static createDynamoDBTestData() {
    return {
      expectedTable: {
        tableName: 'line-bot-conversations',
        partitionKey: { name: 'userId', type: 'S' },
        billingMode: 'PAY_PER_REQUEST',
        ttlAttribute: 'ttl',
        pointInTimeRecovery: false
      }
    };
  }

  /**
   * Creates standardized test data for Step Functions validation
   */
  public static createStepFunctionsTestData() {
    return {
      expectedStateMachine: {
        timeoutSeconds: 300,
        comment: 'Orchestrates AI processing workflow with optional web search',
        expectedStates: [
          'ProcessWithSambaNova',
          'CheckForToolCall',
          'SendInterimResponse',
          'ProcessWithGrok',
          'SendFinalResponse',
          'SendDirectResponse'
        ]
      }
    };
  }

  /**
   * Creates standardized test data for API Gateway validation
   */
  public static createAPIGatewayTestData() {
    return {
      expectedRestApi: {
        binaryMediaTypes: ['*/*'],
        description: 'LINE Bot Webhook API',
        methods: ['ANY']
      }
    };
  }

  /**
   * Creates standardized test data for IAM validation
   */
  public static createIAMTestData() {
    return {
      expectedPermissions: {
        dynamodb: [
          'dynamodb:BatchGetItem',
          'dynamodb:GetRecords',
          'dynamodb:GetShardIterator',
          'dynamodb:Query',
          'dynamodb:GetItem',
          'dynamodb:Scan',
          'dynamodb:ConditionCheckItem',
          'dynamodb:BatchWriteItem',
          'dynamodb:PutItem',
          'dynamodb:UpdateItem',
          'dynamodb:DeleteItem',
          'dynamodb:DescribeTable'
        ],
        secretsmanager: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret'
        ],
        stepfunctions: [
          'states:StartExecution'
        ],
        logs: [
          'logs:CreateLogGroup',
          'logs:CreateLogStream',
          'logs:PutLogEvents'
        ]
      }
    };
  }
}

export class TestValidators {
  /**
   * Validates Lambda function configuration against expected data
   */
  public static validateLambdaFunction(
    template: Template,
    expectedFunction: any
  ): void {
    const lambdaFunctions = template.findResources('AWS::Lambda::Function');
    const actualFunction = Object.values(lambdaFunctions).find((func: any) => 
      func.Properties.Handler === expectedFunction.handler
    );

    expect(actualFunction).toBeDefined();
    if (actualFunction) {
      expect(actualFunction.Properties.Runtime).toBe(expectedFunction.runtime);
      expect(actualFunction.Properties.Description).toBe(expectedFunction.description);
      
      if (expectedFunction.timeout > 3) {
        expect(actualFunction.Properties.Timeout).toBe(expectedFunction.timeout);
      }

      // Validate environment variables
      const envVars = actualFunction.Properties.Environment?.Variables || {};
      
      if (expectedFunction.requiresConversationTable) {
        expect(envVars.CONVERSATION_TABLE_NAME).toBeDefined();
      }
      
      if (expectedFunction.requiresLineCredentials) {
        expect(envVars.CHANNEL_ACCESS_TOKEN_NAME).toBeDefined();
        if (expectedFunction.handler === 'webhook_handler.lambda_handler') {
          expect(envVars.CHANNEL_SECRET_NAME).toBeDefined();
        }
      }
      
      if (expectedFunction.requiresStepFunctionsArn) {
        expect(envVars.STEP_FUNCTION_ARN).toBeDefined();
      }
      
      if (expectedFunction.requiresSambaNovaCredentials) {
        expect(envVars.SAMBA_NOVA_API_KEY_NAME).toBeDefined();
      }
      
      if (expectedFunction.requiresXaiCredentials) {
        expect(envVars.XAI_API_KEY_SECRET_NAME).toBeDefined();
      }
    }
  }

  /**
   * Validates DynamoDB table configuration
   */
  public static validateDynamoDBTable(
    template: Template,
    expectedTable: any
  ): void {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: expectedTable.tableName,
      AttributeDefinitions: [
        {
          AttributeName: expectedTable.partitionKey.name,
          AttributeType: expectedTable.partitionKey.type
        }
      ],
      KeySchema: [
        {
          AttributeName: expectedTable.partitionKey.name,
          KeyType: 'HASH'
        }
      ],
      BillingMode: expectedTable.billingMode,
      TimeToLiveSpecification: {
        AttributeName: expectedTable.ttlAttribute,
        Enabled: true
      },
      PointInTimeRecoverySpecification: {
        PointInTimeRecoveryEnabled: expectedTable.pointInTimeRecovery
      }
    });
  }

  /**
   * Validates Step Functions state machine configuration
   */
  public static validateStepFunctionsStateMachine(
    template: Template,
    expectedStateMachine: any
  ): void {
    template.hasResourceProperties('AWS::StepFunctions::StateMachine', {
      TimeoutSeconds: expectedStateMachine.timeoutSeconds,
      Comment: expectedStateMachine.comment
    });

    const stateMachines = template.findResources('AWS::StepFunctions::StateMachine');
    expect(Object.keys(stateMachines)).toHaveLength(1);

    const definition = JSON.parse((Object.values(stateMachines)[0] as any).Properties.DefinitionString);
    const definitionStr = JSON.stringify(definition);

    expectedStateMachine.expectedStates.forEach((stateName: string) => {
      expect(definitionStr).toContain(stateName);
    });
  }

  /**
   * Validates IAM permissions
   */
  public static validateIAMPermissions(
    template: Template,
    expectedPermissions: any
  ): void {
    const policies = template.findResources('AWS::IAM::Policy');
    
    let foundPermissions = {
      dynamodb: false,
      secretsmanager: false,
      stepfunctions: false,
      logs: false
    };

    Object.values(policies).forEach((policy: any) => {
      const statements = policy.Properties.PolicyDocument.Statement;
      
      statements.forEach((statement: any) => {
        const actions = Array.isArray(statement.Action) ? statement.Action : [statement.Action];
        
        actions.forEach((action: string) => {
          if (action.startsWith('dynamodb:')) {
            foundPermissions.dynamodb = true;
          } else if (action.startsWith('secretsmanager:')) {
            foundPermissions.secretsmanager = true;
          } else if (action.startsWith('states:')) {
            foundPermissions.stepfunctions = true;
          } else if (action.startsWith('logs:')) {
            foundPermissions.logs = true;
          }
        });
      });
    });

    expect(foundPermissions.dynamodb).toBe(true);
    expect(foundPermissions.secretsmanager).toBe(true);
    expect(foundPermissions.stepfunctions).toBe(true);
    expect(foundPermissions.logs).toBe(true);
  }
}

/**
 * Matcher functions for common test patterns
 */
export class TestMatchers {
  /**
   * Matches Lambda function names to handler patterns
   */
  public static matchLambdaHandler(handler: string): boolean {
    return /^[a-z_]+\.lambda_handler$/.test(handler);
  }

  /**
   * Matches CloudFormation logical IDs to naming conventions
   */
  public static matchLogicalId(logicalId: string): boolean {
    return /^[A-Z][a-zA-Z0-9]*$/.test(logicalId);
  }

  /**
   * Matches IAM policy actions to service prefixes
   */
  public static matchServiceAction(action: string, service: string): boolean {
    return action.startsWith(`${service}:`);
  }

  /**
   * Matches resource ARNs to AWS format
   */
  public static matchAWSArn(arn: string): boolean {
    return /^arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]*:.+$/.test(arn);
  }
}

/**
 * Test constants for consistent testing
 */
export const TEST_CONSTANTS = {
  LAMBDA_RUNTIME: 'python3.12',
  DYNAMO_TABLE_NAME: 'line-bot-conversations',
  STEP_FUNCTIONS_TIMEOUT: 300,
  DEFAULT_LAMBDA_TIMEOUT: 3,
  GROK_LAMBDA_TIMEOUT: 180,
  AI_PROCESSOR_TIMEOUT: 15,
  RESPONSE_TIMEOUT: 10,
  EXPECTED_LAMBDA_COUNT: 5,
  EXPECTED_LAYER_COUNT: 1,
  EXPECTED_TABLE_COUNT: 1,
  EXPECTED_STATE_MACHINE_COUNT: 1,
  EXPECTED_API_COUNT: 1
} as const;