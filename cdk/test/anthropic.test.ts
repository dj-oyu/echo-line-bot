import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { LineEchoStack } from '../lib/lambda-stack';

describe('Anthropic routing configuration', () => {
  const originalBackend = process.env.AI_BACKEND;
  const originalModel = process.env.ANTHROPIC_MODEL;

  afterEach(() => {
    if (originalBackend === undefined) delete process.env.AI_BACKEND;
    else process.env.AI_BACKEND = originalBackend;
    if (originalModel === undefined) delete process.env.ANTHROPIC_MODEL;
    else process.env.ANTHROPIC_MODEL = originalModel;
  });

  test('keeps Groq default and passes a secret name, never its value', () => {
    delete process.env.AI_BACKEND;
    delete process.env.ANTHROPIC_MODEL;
    const template = Template.fromStack(new LineEchoStack(new cdk.App(), 'AnthropicDefault'));
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'ai_processor.lambda_handler',
      Environment: { Variables: Match.objectLike({
        AI_BACKEND: 'groq',
        ANTHROPIC_API_KEY_NAME: 'ANTHROPIC_API_KEY',
        ANTHROPIC_MODEL: 'claude-haiku-5-5',
      }) },
    });
    const functions = template.findResources('AWS::Lambda::Function');
    for (const resource of Object.values(functions)) {
      const variables = resource.Properties.Environment.Variables;
      expect(variables.ANTHROPIC_API_KEY).toBeUndefined();
      if (resource.Properties.Handler !== 'ai_processor.lambda_handler') {
        expect(variables.ANTHROPIC_API_KEY_NAME).toBeUndefined();
      }
    }
    const policies = template.findResources('AWS::IAM::Policy');
    const readers = Object.entries(policies).filter(([, policy]) =>
      JSON.stringify(policy.Properties.PolicyDocument).includes('ANTHROPIC_API_KEY')
    );
    expect(readers).toHaveLength(1);
    expect(readers[0][0]).toMatch(/^AiProcessor/);
    expect(JSON.stringify(readers[0][1])).toContain('secretsmanager:GetSecretValue');
  });

  test('forwards an explicit backend and model override', () => {
    process.env.AI_BACKEND = 'anthropic';
    process.env.ANTHROPIC_MODEL = 'test-model-override';
    const template = Template.fromStack(new LineEchoStack(new cdk.App(), 'AnthropicOverride'));
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'ai_processor.lambda_handler',
      Environment: { Variables: Match.objectLike({
        AI_BACKEND: 'anthropic',
        ANTHROPIC_MODEL: 'test-model-override',
      }) },
    });
  });
});
