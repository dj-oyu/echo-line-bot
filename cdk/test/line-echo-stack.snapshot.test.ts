import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { LineEchoStack } from '../lib/lambda-stack';

/**
 * Snapshot Test Suite for LINE Echo Stack
 * 
 * This test suite provides snapshot testing following t_wada's principles:
 * - Regression detection through template comparison
 * - Infrastructure as code validation
 * - Change impact visibility
 * - Template structure verification
 */

describe('LINE Echo Stack - Snapshot Tests', () => {
  let app: cdk.App;
  let stack: LineEchoStack;
  let template: Template;

  beforeEach(() => {
    app = new cdk.App();
    stack = new LineEchoStack(app, 'TestStack', {
      description: 'LINE Echo Bot with AI processing capabilities'
    });
    template = Template.fromStack(stack);
  });

  describe('CloudFormation Template Snapshots', () => {
    test('should match CloudFormation template snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: The CloudFormation template should match the known good snapshot
      
      const templateJson = template.toJSON();
      
      // This will create a snapshot on first run and compare against it on subsequent runs
      expect(templateJson).toMatchSnapshot();
    });

    test('should match Lambda function configurations snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Lambda function configurations should match expected snapshot
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      // Extract and normalize Lambda function configurations for stable snapshots
      const normalizedFunctions = Object.entries(lambdaFunctions).reduce((acc, [key, value]) => {
        acc[key] = {
          Type: value.Type,
          Properties: {
            Handler: value.Properties.Handler,
            Runtime: value.Properties.Runtime,
            Timeout: value.Properties.Timeout,
            Description: value.Properties.Description,
            Environment: value.Properties.Environment ? {
              Variables: Object.keys(value.Properties.Environment.Variables).sort()
            } : undefined
          }
        };
        return acc;
      }, {} as any);
      
      expect(normalizedFunctions).toMatchSnapshot();
    });

    test('should match DynamoDB table configuration snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: DynamoDB table configuration should match expected snapshot
      
      const dynamoTables = template.findResources('AWS::DynamoDB::Table');
      
      // Extract and normalize DynamoDB configuration
      const normalizedTables = Object.entries(dynamoTables).reduce((acc, [key, value]) => {
        acc[key] = {
          Type: value.Type,
          Properties: {
            TableName: value.Properties.TableName,
            AttributeDefinitions: value.Properties.AttributeDefinitions,
            KeySchema: value.Properties.KeySchema,
            BillingMode: value.Properties.BillingMode,
            TimeToLiveSpecification: value.Properties.TimeToLiveSpecification,
            PointInTimeRecoverySpecification: value.Properties.PointInTimeRecoverySpecification
          }
        };
        return acc;
      }, {} as any);
      
      expect(normalizedTables).toMatchSnapshot();
    });

    test('should match Step Functions state machine snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Step Functions configuration should match expected snapshot
      
      const stateMachines = template.findResources('AWS::StepFunctions::StateMachine');
      
      // Extract and normalize Step Functions configuration
      const normalizedStateMachines = Object.entries(stateMachines).reduce((acc, [key, value]) => {
        // Handle DefinitionString which might be a CloudFormation function
        let definition = value.Properties.DefinitionString;
        if (typeof definition === 'string') {
          try {
            definition = JSON.parse(definition);
          } catch (e) {
            // If parsing fails, keep the original string representation
            definition = definition;
          }
        } else if (definition && typeof definition === 'object') {
          // If it's a CloudFormation function (e.g., Fn::Join), keep it as-is
          definition = '[CloudFormation Function]';
        }
        
        acc[key] = {
          Type: value.Type,
          Properties: {
            TimeoutSeconds: value.Properties.TimeoutSeconds,
            Comment: value.Properties.Comment,
            Definition: definition
          }
        };
        return acc;
      }, {} as any);
      
      expect(normalizedStateMachines).toMatchSnapshot();
    });

    test('should match API Gateway configuration snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: API Gateway configuration should match expected snapshot
      
      const restApis = template.findResources('AWS::ApiGateway::RestApi');
      
      // Extract and normalize API Gateway configuration
      const normalizedApis = Object.entries(restApis).reduce((acc, [key, value]) => {
        acc[key] = {
          Type: value.Type,
          Properties: {
            BinaryMediaTypes: value.Properties.BinaryMediaTypes,
            Description: value.Properties.Description,
            Name: value.Properties.Name
          }
        };
        return acc;
      }, {} as any);
      
      expect(normalizedApis).toMatchSnapshot();
    });

    test('should match IAM roles and policies snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: IAM configuration should match expected snapshot
      
      const roles = template.findResources('AWS::IAM::Role');
      const policies = template.findResources('AWS::IAM::Policy');
      
      // Extract and normalize IAM configuration
      const normalizedRoles = Object.entries(roles).reduce((acc, [key, value]) => {
        acc[key] = {
          Type: value.Type,
          Properties: {
            AssumeRolePolicyDocument: value.Properties.AssumeRolePolicyDocument,
            ManagedPolicyArns: value.Properties.ManagedPolicyArns
          }
        };
        return acc;
      }, {} as any);
      
      const normalizedPolicies = Object.entries(policies).reduce((acc, [key, value]) => {
        acc[key] = {
          Type: value.Type,
          Properties: {
            PolicyDocument: value.Properties.PolicyDocument
          }
        };
        return acc;
      }, {} as any);
      
      expect({ roles: normalizedRoles, policies: normalizedPolicies }).toMatchSnapshot();
    });

    test('should match CloudFormation outputs snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: CloudFormation outputs should match expected snapshot
      
      const outputs = template.findOutputs('*');
      
      // Extract and normalize outputs
      const normalizedOutputs = Object.entries(outputs).reduce((acc, [key, value]) => {
        acc[key] = {
          Description: value.Description,
          // Don't include the actual values as they contain references
          HasValue: value.Value !== undefined
        };
        return acc;
      }, {} as any);
      
      expect(normalizedOutputs).toMatchSnapshot();
    });
  });

  describe('Resource Count Snapshots', () => {
    test('should match resource counts snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Resource counts should match expected snapshot
      
      const templateJson = template.toJSON();
      const resources = templateJson.Resources;
      
      // Count resources by type
      const resourceCounts= Object.values(resources).reduce((acc: Record<string, number>, resource: any) => {
        const type = resource.Type;
        acc[type] = (acc[type] || 0) + 1;
        return acc;
      }, {});
      
      // Sort for consistent snapshots
      const sortedResourceCounts = Object.keys(resourceCounts)
        .sort()
        .reduce((acc, key) => {
          acc[key] = resourceCounts[key];
          return acc;
        }, {} as Record<string, number>);
      
      expect(sortedResourceCounts).toMatchSnapshot();
    });

    test('should match Lambda function count and names snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Lambda function count and handler names should match snapshot
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      
      const functionHandlers = Object.values(lambdaFunctions)
        .map((func: any) => func.Properties.Handler)
        .sort();
      
      expect({
        count: functionHandlers.length,
        handlers: functionHandlers
      }).toMatchSnapshot();
    });
  });

  describe('Environment-Specific Snapshots', () => {
    test('should match development environment snapshot', () => {
      // Given: A LINE bot stack is created for development
      // When: The stack is synthesized
      // Then: Development-specific configuration should match snapshot
      
      const devApp = new cdk.App();
      const devStack = new LineEchoStack(devApp, 'DevStack', {
        description: 'LINE Echo Bot - Development Environment'
      });
      const devTemplate = Template.fromStack(devStack);
      
      // Extract development-specific configurations
      const lambdaFunctions = devTemplate.findResources('AWS::Lambda::Function');
      const devConfig = {
        functionCount: Object.keys(lambdaFunctions).length,
        timeouts: Object.values(lambdaFunctions).map((func: any) => func.Properties.Timeout || 3).sort(),
        runtimes: [...new Set(Object.values(lambdaFunctions).map((func: any) => func.Properties.Runtime))].sort()
      };
      
      expect(devConfig).toMatchSnapshot();
    });
  });

  describe('Security Configuration Snapshots', () => {
    test('should match security policies snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Security policies should match expected snapshot
      
      const policies = template.findResources('AWS::IAM::Policy');
      
      // Extract policy actions and resources for security review
      const securityConfig = Object.entries(policies).reduce((acc, [key, policy]) => {
        const statements = policy.Properties.PolicyDocument.Statement;
        
        acc[key] = statements.map((statement: any) => ({
          Effect: statement.Effect,
          Actions: Array.isArray(statement.Action) ? statement.Action.sort() : [statement.Action],
          Resources: Array.isArray(statement.Resource) ? statement.Resource.length : 1
        }));
        
        return acc;
      }, {} as any);
      
      expect(securityConfig).toMatchSnapshot();
    });
  });

  describe('Performance Configuration Snapshots', () => {
    test('should match performance settings snapshot', () => {
      // Given: A LINE bot stack is created
      // When: The stack is synthesized
      // Then: Performance settings should match expected snapshot
      
      const lambdaFunctions = template.findResources('AWS::Lambda::Function');
      const stateMachines = template.findResources('AWS::StepFunctions::StateMachine');
      const dynamoTables = template.findResources('AWS::DynamoDB::Table');
      
      const performanceConfig = {
        lambda: {
          timeouts: Object.values(lambdaFunctions).map((func: any) => ({
            handler: func.Properties.Handler,
            timeout: func.Properties.Timeout || 3
          })).sort((a, b) => a.handler.localeCompare(b.handler))
        },
        stepFunctions: {
          timeouts: Object.values(stateMachines).map((sm: any) => sm.Properties.TimeoutSeconds || 300)
        },
        dynamodb: {
          billingModes: Object.values(dynamoTables).map((table: any) => table.Properties.BillingMode)
        }
      };
      
      expect(performanceConfig).toMatchSnapshot();
    });
  });
});