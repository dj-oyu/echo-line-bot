---
description: TypeScript CDK development rules
globs: ["cdk/**/*.ts"]
alwaysApply: false
---

# TypeScript CDK Development Rules

## Runtime & Tools

- **Node.js**: 20
- **Package Manager**: pnpm
- **Framework**: AWS CDK (aws-cdk-lib)

## Code Style

### Strict Mode
TypeScript strict mode is enabled. Always:
- Use explicit types
- Handle null/undefined properly
- Avoid `any` type

### Method Organization
Organize stack classes with private methods:
```typescript
export class LineEchoStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const table = this.createConversationTable();
    const secrets = this.createSecretReferences();
    // ...
  }

  private createConversationTable(): dynamodb.Table {
    // ...
  }

  private createSecretReferences() {
    // ...
  }
}
```

### JSDoc Comments
Add JSDoc for public methods and complex logic:
```typescript
/**
 * Creates DynamoDB table for conversation history with TTL
 */
private createConversationTable(): dynamodb.Table {
  // ...
}
```

## CDK Patterns

### Resource Naming
Use descriptive construct IDs:
```typescript
new lambda.Function(this, 'WebhookHandler', { ... });
new dynamodb.Table(this, 'ConversationHistory', { ... });
```

### Secrets Manager
Reference existing secrets (created by GitHub Actions):
```typescript
secretsmanager.Secret.fromSecretNameV2(
  this,
  'LineChannelSecret',
  'LINE_CHANNEL_SECRET'
);
```

### Lambda Configuration
```typescript
const baseConfig = {
  runtime: lambda.Runtime.PYTHON_3_12,
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
  layers: [dependenciesLayer],
};
```

### CloudFormation Outputs
Always output important resources:
```typescript
new cdk.CfnOutput(this, 'ApiGatewayUrl', {
  value: api.url,
  description: 'API Gateway URL for LINE webhook'
});
```

## Commands

```bash
cd cdk

# Development
pnpm install          # Install dependencies
pnpm run build        # Compile TypeScript
pnpm run watch        # Watch mode

# Testing
pnpm test             # Run Jest tests
pnpm test -- -u       # Update snapshots

# CDK Operations
pnpm run cdk synth    # Generate CloudFormation
pnpm run cdk diff     # Show changes
pnpm run cdk deploy   # Deploy to AWS
```

## Testing

Write tests in `cdk/test/`:
```typescript
test('Lambda function created with correct runtime', () => {
  const app = new cdk.App();
  const stack = new LineEchoStack(app, 'TestStack');
  const template = Template.fromStack(stack);

  template.hasResourceProperties('AWS::Lambda::Function', {
    Runtime: 'python3.12',
  });
});
```
