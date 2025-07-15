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

  test('DynamoDB table created', () => {
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

  // Note: Lambda layer removed to avoid Docker dependency in tests

  test('Correct number of resources created', () => {
    // Check resource counts without hardcoding resource names
    template.resourceCountIs('AWS::Lambda::Function', 5); // webhook, ai, response, interim_response_sender, more
    template.resourceCountIs('AWS::DynamoDB::Table', 1);
    template.resourceCountIs('AWS::StepFunctions::StateMachine', 1);
    template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
    // Note: No longer using Lambda layer
  });

  test('All Lambda functions have correct runtime', () => {
    const lambdaFunctions = template.findResources('AWS::Lambda::Function');
    
    // Check that all Lambda functions use Python 3.12
    Object.values(lambdaFunctions).forEach((func: any) => {
      expect(func.Properties.Runtime).toBe('python3.12');
    });
  });
});
