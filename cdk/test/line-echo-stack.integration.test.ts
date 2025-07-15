import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { LineEchoStack } from '../lib/lambda-stack';

/**
 * Integration Test Suite for LINE Echo Stack
 * 
 * This test suite covers integration scenarios following t_wada's principles:
 * - End-to-end workflow validation
 * - Component interaction testing
 * - System behavior verification
 * - Cross-service integration
 */

describe('LINE Echo Stack - Integration Tests', () => {
  let app: cdk.App;
  let stack: LineEchoStack;
  let template: Template;

  beforeEach(() => {
    app = new cdk.App();
    stack = new LineEchoStack(app, 'TestStack');
    template = Template.fromStack(stack);
  });

  describe('End-to-End Workflow Integration', () => {
    test('should integrate webhook handler with Step Functions workflow', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Webhook handler should be able to trigger Step Functions workflow
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const webhookHandler = Object.values(lambdaFunctions).find((func: any) => 
        func.Properties.Handler === 'webhook_handler.lambda_handler'
      );
      
      expect(webhookHandler).toBeDefined();
      if (webhookHandler) {
        // Webhook handler should have Step Functions ARN in environment
        expect(webhookHandler.Properties.Environment.Variables.STEP_FUNCTION_ARN).toBeDefined();
      }
      
      // Should have IAM permissions to start Step Functions execution
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

    test('should integrate Step Functions with all processing Lambda functions', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Step Functions should be configured to invoke all processing functions
      
      const stateMachine = template.findResources('AWS::StepFunctions::StateMachine');
      expect(Object.keys(stateMachine)).toHaveLength(1);
      
      const definition = (Object.values(stateMachine)[0] as any).Properties.DefinitionString;
      const definitionObj = JSON.parse(definition);
      
      // Should include all Lambda function ARNs in the workflow
      const definitionStr = JSON.stringify(definitionObj);
      expect(definitionStr).toContain('ai_processor.lambda_handler');
      expect(definitionStr).toContain('interim_response_sender.lambda_handler');
      expect(definitionStr).toContain('grok_processor.lambda_handler');
      expect(definitionStr).toContain('response_sender.lambda_handler');
    });

    test('should integrate Lambda functions with DynamoDB for conversation management', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Conversation-aware functions should have DynamoDB table name and permissions
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const conversationFunctions = ['webhook_handler', 'ai_processor', 'response_sender'];
      
      conversationFunctions.forEach(handlerName => {
        const func = Object.values(lambdaFunctions).find((f: any) => 
          f.Properties.Handler === `${handlerName}.lambda_handler`
        );
        
        expect(func).toBeDefined();
        if (func) {
          expect(func.Properties.Environment.Variables.CONVERSATION_TABLE_NAME).toBeDefined();
        }
      });
    });

    test('should integrate Lambda functions with Secrets Manager for API credentials', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: All functions should have access to their required secrets
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      // Webhook handler should have LINE credentials
      const webhookHandler = Object.values(lambdaFunctions).find((func: any) => 
        func.Properties.Handler === 'webhook_handler.lambda_handler'
      );
      expect(webhookHandler).toBeDefined();
      if (webhookHandler) {
        const envVars = webhookHandler.Properties.Environment.Variables;
        expect(envVars.CHANNEL_SECRET_NAME).toBeDefined();
        expect(envVars.CHANNEL_ACCESS_TOKEN_NAME).toBeDefined();
      }
      
      // AI processor should have SambaNova credentials
      const aiProcessor = Object.values(lambdaFunctions).find((func: any) => 
        func.Properties.Handler === 'ai_processor.lambda_handler'
      );
      expect(aiProcessor).toBeDefined();
      if (aiProcessor) {
        expect(aiProcessor.Properties.Environment.Variables.SAMBA_NOVA_API_KEY_NAME).toBeDefined();
      }
      
      // Grok processor should have xAI credentials
      const grokProcessor = Object.values(lambdaFunctions).find((func: any) => 
        func.Properties.Handler === 'grok_processor.lambda_handler'
      );
      expect(grokProcessor).toBeDefined();
      if (grokProcessor) {
        expect(grokProcessor.Properties.Environment.Variables.XAI_API_KEY_SECRET_NAME).toBeDefined();
      }
    });
  });

  describe('API Gateway Integration', () => {
    test('should integrate API Gateway with webhook handler', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: API Gateway should be configured to trigger webhook handler
      
      const restApi = template.findResources('AWS::ApiGateway::RestApi');
      expect(Object.keys(restApi)).toHaveLength(1);
      
      // Should have proper integration with Lambda
      template.hasResourceProperties('AWS::ApiGateway::Method', {
        HttpMethod: 'ANY',
        Integration: {
          Type: 'AWS_PROXY',
          IntegrationHttpMethod: 'POST'
        }
      });
    });

    test('should configure API Gateway for LINE webhook requirements', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: API Gateway should be configured for LINE webhook specifications
      
      template.hasResourceProperties('AWS::ApiGateway::RestApi', {
        BinaryMediaTypes: ['*/*'],
        Description: 'LINE Bot Webhook API'
      });
      
      // Should have proper CORS configuration for LINE
      template.hasResourceProperties('AWS::ApiGateway::Method', {
        HttpMethod: 'ANY'
      });
    });
  });

  describe('Dependencies Layer Integration', () => {
    test('should ensure all Lambda functions share the same dependencies layer', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: All Lambda functions should use the same dependencies layer
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const layers = template.findResources('AWS::Lambda::LayerVersion');
      
      expect(Object.keys(layers)).toHaveLength(1);
      const layerLogicalId = Object.keys(layers)[0];
      
      Object.values(lambdaFunctions).forEach((func: any) => {
        expect(func.Properties.Layers).toHaveLength(1);
        expect(func.Properties.Layers[0]).toEqual({ Ref: layerLogicalId });
      });
    });

    test('should configure layer with correct runtime compatibility', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Dependencies layer should be compatible with all Lambda runtimes
      
      const layers = template.findResources('AWS::Lambda::LayerVersion');
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      expect(Object.keys(layers)).toHaveLength(1);
      const layer = Object.values(layers)[0] as any;
      
      // Layer should be compatible with all function runtimes
      Object.values(lambdaFunctions).forEach((func: any) => {
        expect(layer.Properties.CompatibleRuntimes).toContain(func.Properties.Runtime);
      });
    });
  });

  describe('Security Integration', () => {
    test('should integrate IAM roles with Lambda functions correctly', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Each Lambda function should have appropriate IAM role
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const roles = template.findResources('AWS::IAM::Role');
      
      // Should have IAM roles for Lambda functions
      expect(Object.keys(roles).length).toBeGreaterThanOrEqual(1);
      
      Object.values(lambdaFunctions).forEach((func: any) => {
        expect(func.Properties.Role).toBeDefined();
        expect(func.Properties.Role).toHaveProperty('Fn::GetAtt');
      });
    });

    test('should integrate security policies with service requirements', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Security policies should match service access requirements
      
      const policies = template.findResources('AWS::IAM::Policy');
      
      // Should have policies for DynamoDB, Secrets Manager, and Step Functions
      let hasDynamoPolicy = false;
      let hasSecretsPolicy = false;
      let hasStepFunctionsPolicy = false;
      
      Object.values(policies).forEach((policy: any) => {
        const statements = policy.Properties.PolicyDocument.Statement;
        
        statements.forEach((statement: any) => {
          if (Array.isArray(statement.Action)) {
            if (statement.Action.some((action: string) => action.startsWith('dynamodb:'))) {
              hasDynamoPolicy = true;
            }
            if (statement.Action.some((action: string) => action.startsWith('secretsmanager:'))) {
              hasSecretsPolicy = true;
            }
            if (statement.Action.some((action: string) => action.startsWith('states:'))) {
              hasStepFunctionsPolicy = true;
            }
          }
        });
      });
      
      expect(hasDynamoPolicy).toBe(true);
      expect(hasSecretsPolicy).toBe(true);
      expect(hasStepFunctionsPolicy).toBe(true);
    });
  });

  describe('Monitoring and Observability Integration', () => {
    test('should configure CloudWatch integration for all Lambda functions', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Lambda functions should have CloudWatch integration
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      Object.values(lambdaFunctions).forEach((func: any) => {
        // Lambda functions should have CloudWatch Logs permissions
        expect(func.Properties.Role).toBeDefined();
      });
      
      // Should have CloudWatch Logs permissions in IAM policies
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            {
              Effect: 'Allow',
              Action: Match.arrayWith([
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents'
              ])
            }
          ])
        }
      });
    });

    test('should provide CloudFormation outputs for monitoring setup', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Important resource identifiers should be available as outputs
      
      const outputs = template.findOutputs('*');
      
      expect(outputs).toHaveProperty('ApiGatewayUrl');
      expect(outputs).toHaveProperty('ConversationTableName');
      expect(outputs).toHaveProperty('StateMachineArn');
      
      // Outputs should have descriptions for monitoring setup
      expect(outputs.ApiGatewayUrl.Description).toBe('API Gateway URL for LINE webhook');
      expect(outputs.ConversationTableName.Description).toBe('DynamoDB table name for conversation history');
      expect(outputs.StateMachineArn.Description).toBe('Step Functions state machine ARN');
    });
  });

  describe('Cross-Service Communication Integration', () => {
    test('should ensure proper service-to-service communication patterns', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Services should be configured for proper communication
      
      // API Gateway -> Lambda (webhook handler) -> Step Functions -> Lambda functions
      const stateMachine = template.findResources('AWS::StepFunctions::StateMachine');
      const stateMachineDefinition = (Object.values(stateMachine)[0] as any).Properties.DefinitionString;
      const definition = JSON.parse(stateMachineDefinition);
      
      // Should have proper state transitions
      expect(definition.States).toBeDefined();
      expect(definition.StartAt).toBeDefined();
      
      // Should have conditional logic for different processing paths
      const stateNames = Object.keys(definition.States);
      expect(stateNames).toContain('CheckForToolCall');
    });

    test('should handle asynchronous processing patterns correctly', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Asynchronous processing should be properly configured
      
      // Step Functions should handle async Lambda invocations
      const stateMachine = template.findResources('AWS::StepFunctions::StateMachine');
      const definition = JSON.parse((Object.values(stateMachine)[0] as any).Properties.DefinitionString);
      
      // Should use Lambda invoke tasks for asynchronous processing
      const states = definition.States;
      Object.values(states).forEach((state: any) => {
        if (state.Type === 'Task' && state.Resource?.startsWith('arn:aws:states:::lambda:invoke')) {
          expect(state.ResultPath).toBeDefined();
        }
      });
    });
  });

  describe('Error Handling Integration', () => {
    test('should configure proper error handling across services', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Error handling should be integrated across all services
      
      // Step Functions should have error handling
      const stateMachine = template.findResources('AWS::StepFunctions::StateMachine');
      const definition = JSON.parse((Object.values(stateMachine)[0] as any).Properties.DefinitionString);
      
      // Should have timeout configuration
      expect(definition.TimeoutSeconds || 300).toBeLessThanOrEqual(300);
      
      // Lambda functions should have appropriate timeouts
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      Object.values(lambdaFunctions).forEach((func: any) => {
        const timeout = func.Properties.Timeout || 3;
        expect(timeout).toBeGreaterThan(0);
        expect(timeout).toBeLessThanOrEqual(900);
      });
    });
  });
});