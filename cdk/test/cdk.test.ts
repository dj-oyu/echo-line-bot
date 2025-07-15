import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { LineEchoStack } from '../lib/lambda-stack';

// Mock environment variables for testing
process.env.CHANNEL_ACCESS_TOKEN = 'test-channel-token';
process.env.CHANNEL_SECRET = 'test-channel-secret';
process.env.SAMBA_NOVA_API_KEY = 'test-samba-nova-key';

describe('LineEchoStack', () => {
  let app: cdk.App;
  let stack: LineEchoStack;
  let template: Template;

  beforeEach(() => {
    app = new cdk.App();
    stack = new LineEchoStack(app, 'TestStack');
    template = Template.fromStack(stack);
  });

  test('DynamoDB table created (default behavior)', () => {
    // Default behavior: create new table (useExistingTable context not set)
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'line-bot-conversations',
      BillingMode: 'PAY_PER_REQUEST',
      TimeToLiveSpecification: {
        AttributeName: 'ttl',
        Enabled: true
      }
    });
  });

  test('Lambda functions created', () => {
    // Check webhook handler
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'webhook_handler.lambda_handler',
      Runtime: 'python3.12'
    });

    // Check AI processor
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'ai_processor.lambda_handler',
      Runtime: 'python3.12',
      Timeout: 15
    });

    // Check interim response sender
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'interim_response_sender.lambda_handler',
      Runtime: 'python3.12',
      Timeout: 10
    });

    // Check grok processor
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'grok_processor.lambda_handler',
      Runtime: 'python3.12',
      Timeout: 60
    });

    // Check response sender
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'response_sender.lambda_handler',
      Runtime: 'python3.12',
      Timeout: 10
    });
  });

  test('Step Functions state machine created', () => {
    // Check that exactly one Step Functions state machine exists
    template.resourceCountIs('AWS::StepFunctions::StateMachine', 1);
  });

  test('API Gateway created', () => {
    template.hasResourceProperties('AWS::ApiGateway::RestApi', {});
  });

  test('Lambda Layer created', () => {
    template.hasResourceProperties('AWS::Lambda::LayerVersion', {
      CompatibleRuntimes: ['python3.12'],
      Description: 'Python dependencies for LINE bot Lambda functions'
    });
  });

  test('All Lambda functions use the dependencies layer', () => {
    const lambdaFunctions = template.findResources('AWS::Lambda::Function');
    
    // Verify each Lambda function has the dependencies layer attached
    Object.values(lambdaFunctions).forEach((func: any) => {
      expect(func.Properties.Layers).toBeDefined();
      expect(func.Properties.Layers).toHaveLength(1);
      // The layer reference should be a CloudFormation Ref to the DependenciesLayer
      expect(func.Properties.Layers[0]).toHaveProperty('Ref');
    });
  });

  test('Correct number of resources created', () => {
    // Check resource counts without hardcoding resource names
    template.resourceCountIs('AWS::Lambda::Function', 5); // webhook, ai, response, interim_response_sender, grok
    template.resourceCountIs('AWS::Lambda::LayerVersion', 1); // dependencies layer
    template.resourceCountIs('AWS::DynamoDB::Table', 1); // table created by default
    template.resourceCountIs('AWS::StepFunctions::StateMachine', 1);
    template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
  });

  test('All Lambda functions have correct runtime', () => {
    const lambdaFunctions = template.findResources('AWS::Lambda::Function');
    
    // Check that all Lambda functions use Python 3.12
    Object.values(lambdaFunctions).forEach((func: any) => {
      expect(func.Properties.Runtime).toBe('python3.12');
    });
  });

  test('Grok processor has correct configuration', () => {
    // Verify grok processor exists with specific timeout
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'grok_processor.lambda_handler',
      Runtime: 'python3.12',
      Timeout: 60
    });

    // Verify grok processor has XAI API environment variable
    const lambdaFunctions = template.findResources('AWS::Lambda::Function');
    const grokProcessor = Object.values(lambdaFunctions).find((func: any) => 
      func.Properties.Handler === 'grok_processor.lambda_handler'
    );
    
    expect(grokProcessor).toBeDefined();
    if (grokProcessor) {
      expect(grokProcessor.Properties.Environment.Variables.XAI_API_KEY_SECRET_NAME).toBeDefined();
    }
  });

  test('All Lambda functions have environment variables', () => {
    const lambdaFunctions = template.findResources('AWS::Lambda::Function');
    
    // Verify each Lambda function has environment variables defined
    Object.values(lambdaFunctions).forEach((func: any) => {
      expect(func.Properties.Environment).toBeDefined();
      expect(func.Properties.Environment.Variables).toBeDefined();
      expect(Object.keys(func.Properties.Environment.Variables).length).toBeGreaterThan(0);
    });
  });
});
