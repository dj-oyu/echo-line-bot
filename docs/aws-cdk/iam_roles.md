# Managing IAM Roles

AWS Identity and Access Management (IAM) is a crucial part of securing our application. Every Lambda function needs an IAM Role that grants it permission to interact with other AWS services.

## 1. The Default Execution Role

In this project, we do not explicitly define an IAM Role for our Lambda function in the `lib/lambda-stack.ts` file. When you define a `lambda.Function` construct without specifying a `role` property, **the AWS CDK automatically creates a new IAM Role for you.**

This default role is granted the minimum necessary permissions for a Lambda function to operate. These permissions are defined by the `AWSLambdaBasicExecutionRole` managed policy and include:

- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`

This allows our function to write logs to Amazon CloudWatch, which is essential for debugging and monitoring.

## 2. The Principle of Least Privilege

This automatic role creation follows the **principle of least privilege**. The function is only given the permissions it needs to run, and nothing more. Our echo bot only needs to log its activity, so the default role is sufficient.

If, in the future, the bot needs to interact with other AWS services (e.g., read from an S3 bucket or write to a DynamoDB table), we would need to grant additional permissions to its execution role.

## 3. Adding Permissions

The CDK provides convenient, high-level methods for adding permissions to a role. Instead of manually creating IAM Policy documents, you can use the `grant*` methods on the resource constructs.

### Example: Granting S3 Read Access

Imagine we want our Lambda function to read from an S3 bucket. Here's how we would grant the necessary permission:

```typescript
// 1. Define the S3 Bucket construct
const myBucket = new s3.Bucket(this, 'MyDataBucket');

// 2. Define the Lambda function
const lambdaFunc = new lambda.Function(this, 'lineEchoBot', {
  // ... other properties
});

// 3. Grant read access to the bucket
// This automatically adds the necessary permissions (s3:GetObject)
// to the Lambda function's execution role.
myBucket.grantRead(lambdaFunc);
```

This approach is much safer and easier than writing IAM policies by hand. The CDK figures out which permissions are needed and attaches them to the function's role.

If you need to add a permission that doesn't have a high-level `grant*` method, you can use the `addToRolePolicy` method on the function's role property (`lambdaFunc.role`).
