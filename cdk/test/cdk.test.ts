import { TestStackBuilder, TestDataFactory, TestValidators, TEST_CONSTANTS } from './test-utils';

/**
 * Legacy Test Suite (Refactored)
 * 
 * This test suite has been refactored to use the new test utilities
 * following t_wada's principles for better maintainability and consistency.
 * 
 * @deprecated This file contains legacy tests. Consider using the new comprehensive test suites instead.
 */

describe('LineEchoStack - Legacy Tests (Refactored)', () => {
  describe('Basic Resource Creation', () => {
    test('should create DynamoDB table with default configuration', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: A DynamoDB table should be created with proper configuration
      const expectedTable = TestDataFactory.createDynamoDBTestData().expectedTable;
      TestValidators.validateDynamoDBTable(template, expectedTable);
    });

    test('should create all required Lambda functions', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: All Lambda functions should be created with proper configuration
      const { expectedFunctions } = TestDataFactory.createLambdaTestData();
      
      expectedFunctions.forEach(expectedFunction => {
        TestValidators.validateLambdaFunction(template, expectedFunction);
      });
    });

    test('should create Step Functions state machine', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: A Step Functions state machine should be created
      const expectedStateMachine = TestDataFactory.createStepFunctionsTestData().expectedStateMachine;
      TestValidators.validateStepFunctionsStateMachine(template, expectedStateMachine);
    });

    test('should create API Gateway', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: An API Gateway should be created
      const expectedApi = TestDataFactory.createAPIGatewayTestData().expectedRestApi;
      
      template.hasResourceProperties('AWS::ApiGateway::RestApi', {
        BinaryMediaTypes: expectedApi.binaryMediaTypes,
        Description: expectedApi.description
      });
    });

    test('should create Lambda Layer with correct configuration', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: A Lambda layer should be created
      template.hasResourceProperties('AWS::Lambda::LayerVersion', {
        CompatibleRuntimes: [TEST_CONSTANTS.LAMBDA_RUNTIME],
        Description: 'Python dependencies for LINE bot Lambda functions'
      });
    });

    test('should ensure all Lambda functions use the dependencies layer', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: All Lambda functions should use the dependencies layer
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      Object.values(lambdaFunctions).forEach((func: any) => {
        expect(func.Properties.Layers).toBeDefined();
        expect(func.Properties.Layers).toHaveLength(1);
        expect(func.Properties.Layers[0]).toHaveProperty('Ref');
      });
    });

    test('should create correct number of resources', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: The correct number of each resource type should be created
      template.resourceCountIs('AWS::Lambda::Function', TEST_CONSTANTS.EXPECTED_LAMBDA_COUNT);
      template.resourceCountIs('AWS::Lambda::LayerVersion', TEST_CONSTANTS.EXPECTED_LAYER_COUNT);
      template.resourceCountIs('AWS::DynamoDB::Table', TEST_CONSTANTS.EXPECTED_TABLE_COUNT);
      template.resourceCountIs('AWS::StepFunctions::StateMachine', TEST_CONSTANTS.EXPECTED_STATE_MACHINE_COUNT);
      template.resourceCountIs('AWS::ApiGateway::RestApi', TEST_CONSTANTS.EXPECTED_API_COUNT);
    });

    test('should ensure all Lambda functions have correct runtime', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: All Lambda functions should use the correct runtime
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      Object.values(lambdaFunctions).forEach((func: any) => {
        expect(func.Properties.Runtime).toBe(TEST_CONSTANTS.LAMBDA_RUNTIME);
      });
    });

    test('should configure Grok processor correctly', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: Grok processor should have correct configuration
      const grokFunction = TestDataFactory.createLambdaTestData().expectedFunctions
        .find(f => f.handler === 'grok_processor.lambda_handler');
      
      if (grokFunction) {
        TestValidators.validateLambdaFunction(template, grokFunction);
      }
    });

    test('should ensure all Lambda functions have environment variables', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: All Lambda functions should have environment variables
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      Object.values(lambdaFunctions).forEach((func: any) => {
        expect(func.Properties.Environment).toBeDefined();
        expect(func.Properties.Environment.Variables).toBeDefined();
        expect(Object.keys(func.Properties.Environment.Variables).length).toBeGreaterThan(0);
      });
    });

    test('should configure proper IAM permissions', () => {
      // Given: A LINE bot stack is created
      const { template } = new TestStackBuilder().build();
      
      // When: The stack is synthesized
      // Then: IAM permissions should be properly configured
      const expectedPermissions = TestDataFactory.createIAMTestData().expectedPermissions;
      TestValidators.validateIAMPermissions(template, expectedPermissions);
    });
  });
});
