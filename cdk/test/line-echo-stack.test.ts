import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { LineEchoStack } from '../lib/lambda-stack';

/**
 * Test suite for LINE Echo Stack
 * 
 * This test suite follows t_wada's testing principles:
 * - Clear test intention with descriptive names
 * - Given-When-Then pattern
 * - Comprehensive coverage including edge cases
 * - Tests as documentation
 */

describe('LINE Echo Stack', () => {
  let app: cdk.App;
  let stack: LineEchoStack;
  let template: Template;

  beforeEach(() => {
    app = new cdk.App();
    stack = new LineEchoStack(app, 'TestStack');
    template = Template.fromStack(stack);
  });

  describe('DynamoDB Configuration', () => {
    test('should create conversation table with proper TTL configuration', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: A DynamoDB table should be created with TTL for automatic cleanup
      
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'line-bot-conversations',
        AttributeDefinitions: [
          {
            AttributeName: 'userId',
            AttributeType: 'S'
          }
        ],
        KeySchema: [
          {
            AttributeName: 'userId',
            KeyType: 'HASH'
          }
        ],
        BillingMode: 'PAY_PER_REQUEST',
        TimeToLiveSpecification: {
          AttributeName: 'ttl',
          Enabled: true
        }
      });
    });

    test('should configure table with cost-optimized settings', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: The DynamoDB table should be configured for cost optimization
      
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        BillingMode: 'PAY_PER_REQUEST',
        PointInTimeRecoverySpecification: {
          PointInTimeRecoveryEnabled: false
        }
      });
    });
  });

  describe('Lambda Functions Configuration', () => {
    test('should create webhook handler with proper timeout for LINE webhook constraints', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Webhook handler should be created with default timeout (suitable for LINE's 5-second limit)
      
      template.hasResourceProperties('AWS::Lambda::Function', {
        Handler: 'webhook_handler.lambda_handler',
        Runtime: 'python3.12',
        Description: 'Handles LINE webhook events and initiates AI processing',
        // Default timeout is 3 seconds, which is well within LINE's 5-second limit
        Timeout: Match.absent() // Uses CDK default of 3 seconds
      });
    });

    test('should create AI processor with sufficient timeout for API calls', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: AI processor should have 15-second timeout for SambaNova API calls
      
      template.hasResourceProperties('AWS::Lambda::Function', {
        Handler: 'ai_processor.lambda_handler',
        Runtime: 'python3.12',
        Description: 'Processes user messages using SambaNova AI',
        Timeout: 15
      });
    });

    test('should create Grok processor with extended timeout for web searches', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Grok processor should have 180-second timeout for potentially long web searches
      
      template.hasResourceProperties('AWS::Lambda::Function', {
        Handler: 'grok_processor.lambda_handler',
        Runtime: 'python3.12',
        Description: 'Processes queries using Grok AI for web search',
        Timeout: 180
      });
    });

    test('should create response senders with fast timeout for message delivery', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Response senders should have 10-second timeout for quick message delivery
      
      template.hasResourceProperties('AWS::Lambda::Function', {
        Handler: 'response_sender.lambda_handler',
        Runtime: 'python3.12',
        Description: 'Sends final response to LINE and saves conversation history',
        Timeout: 10
      });

      template.hasResourceProperties('AWS::Lambda::Function', {
        Handler: 'interim_response_sender.lambda_handler',
        Runtime: 'python3.12',
        Description: 'Sends interim response while processing complex queries',
        Timeout: 10
      });
    });

    test('should ensure all Lambda functions use consistent Python runtime', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: All Lambda functions should use Python 3.12 for consistency
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const functionCount = Object.keys(lambdaFunctions).length;
      
      expect(functionCount).toBe(5);
      
      Object.values(lambdaFunctions).forEach((func: any) => {
        expect(func.Properties.Runtime).toBe('python3.12');
      });
    });

    test('should attach dependencies layer to all Lambda functions', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: All Lambda functions should have the dependencies layer attached
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      Object.values(lambdaFunctions).forEach((func: any) => {
        expect(func.Properties.Layers).toBeDefined();
        expect(func.Properties.Layers).toHaveLength(1);
        expect(func.Properties.Layers[0]).toHaveProperty('Ref');
      });
    });
  });

  describe('Environment Variables Configuration', () => {
    test('should configure webhook handler with required secrets', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Webhook handler should have access to LINE credentials and conversation table
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const webhookHandler = Object.values(lambdaFunctions).find((func: any) => 
        func.Properties.Handler === 'webhook_handler.lambda_handler'
      );
      
      expect(webhookHandler).toBeDefined();
      if (webhookHandler) {
        const envVars = webhookHandler.Properties.Environment.Variables;
        expect(envVars.CONVERSATION_TABLE_NAME).toBeDefined();
        expect(envVars.CHANNEL_SECRET_NAME).toBeDefined();
        expect(envVars.CHANNEL_ACCESS_TOKEN_NAME).toBeDefined();
        expect(envVars.STEP_FUNCTION_ARN).toBeDefined();
      }
    });

    test('should configure AI processor with SambaNova API access', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: AI processor should have access to SambaNova API key and conversation table
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const aiProcessor = Object.values(lambdaFunctions).find((func: any) => 
        func.Properties.Handler === 'ai_processor.lambda_handler'
      );
      
      expect(aiProcessor).toBeDefined();
      if (aiProcessor) {
        const envVars = aiProcessor.Properties.Environment.Variables;
        expect(envVars.CONVERSATION_TABLE_NAME).toBeDefined();
        expect(envVars.SAMBA_NOVA_API_KEY_NAME).toBeDefined();
      }
    });

    test('should configure Grok processor with xAI API access', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Grok processor should have access to xAI API key
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const grokProcessor = Object.values(lambdaFunctions).find((func: any) => 
        func.Properties.Handler === 'grok_processor.lambda_handler'
      );
      
      expect(grokProcessor).toBeDefined();
      if (grokProcessor) {
        const envVars = grokProcessor.Properties.Environment.Variables;
        expect(envVars.XAI_API_KEY_SECRET_NAME).toBeDefined();
      }
    });
  });

  describe('IAM Permissions Configuration', () => {
    test('should grant DynamoDB permissions to conversation-aware Lambda functions', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Functions that handle conversations should have DynamoDB permissions
      
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            {
              Effect: 'Allow',
              Action: [
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
              Resource: [
                Match.anyValue(),
                Match.anyValue()
              ]
            }
          ])
        }
      });
    });

    test('should grant Secrets Manager permissions to all Lambda functions', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: All Lambda functions should have access to their required secrets
      
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            {
              Effect: 'Allow',
              Action: [
                'secretsmanager:GetSecretValue',
                'secretsmanager:DescribeSecret'
              ],
              Resource: Match.anyValue()
            }
          ])
        }
      });
    });

    test('should grant Step Functions execution permissions to webhook handler', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Webhook handler should be able to start Step Functions executions
      
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            {
              Effect: 'Allow',
              Action: 'states:StartExecution',
              Resource: Match.anyValue()
            }
          ])
        }
      });
    });
  });

  describe('Step Functions Workflow Configuration', () => {
    test('should create AI processing workflow with proper timeout', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Step Functions workflow should be created with 5-minute timeout
      
      template.hasResourceProperties('AWS::StepFunctions::StateMachine', {
        TimeoutSeconds: 300, // 5 minutes
        Comment: 'Orchestrates AI processing workflow with optional web search'
      });
    });

    test('should configure workflow with conditional Grok processing', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Workflow should have conditional logic for Grok processing
      
      template.hasResourceProperties('AWS::StepFunctions::StateMachine', {
        DefinitionString: Match.stringLikeRegexp('.*CheckForToolCall.*'),
      });
    });
  });

  describe('API Gateway Configuration', () => {
    test('should create REST API with binary media type support', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: API Gateway should support binary media types for LINE webhook
      
      template.hasResourceProperties('AWS::ApiGateway::RestApi', {
        BinaryMediaTypes: ['*/*'],
        Description: 'LINE Bot Webhook API'
      });
    });

    test('should create exactly one API Gateway for the webhook', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Exactly one API Gateway should be created
      
      template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
    });
  });

  describe('Dependencies Layer Configuration', () => {
    test('should create layer with Python 3.12 compatibility', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Dependencies layer should be compatible with Python 3.12
      
      template.hasResourceProperties('AWS::Lambda::LayerVersion', {
        CompatibleRuntimes: ['python3.12'],
        Description: 'Python dependencies for LINE bot Lambda functions'
      });
    });

    test('should create exactly one dependencies layer', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Exactly one layer should be created to avoid duplication
      
      template.resourceCountIs('AWS::Lambda::LayerVersion', 1);
    });
  });

  describe('CloudFormation Outputs Configuration', () => {
    test('should output API Gateway URL for LINE webhook configuration', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: API Gateway URL should be available as output
      
      template.hasOutput('ApiGatewayUrl', {
        Description: 'API Gateway URL for LINE webhook'
      });
    });

    test('should output conversation table name for monitoring', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Conversation table name should be available as output
      
      template.hasOutput('ConversationTableName', {
        Description: 'DynamoDB table name for conversation history'
      });
    });

    test('should output Step Functions ARN for monitoring', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Step Functions ARN should be available as output
      
      template.hasOutput('StateMachineArn', {
        Description: 'Step Functions state machine ARN'
      });
    });
  });

  describe('Resource Count Validation', () => {
    test('should create exactly the expected number of resources', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: The correct number of each resource type should be created
      
      template.resourceCountIs('AWS::Lambda::Function', 5);
      template.resourceCountIs('AWS::Lambda::LayerVersion', 1);
      template.resourceCountIs('AWS::DynamoDB::Table', 1);
      template.resourceCountIs('AWS::StepFunctions::StateMachine', 1);
      template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
    });
  });

  describe('Secret References Configuration', () => {
    test('should reference existing secrets without creating new ones', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: No new secrets should be created (they should be referenced)
      
      template.resourceCountIs('AWS::SecretsManager::Secret', 0);
    });
  });
});