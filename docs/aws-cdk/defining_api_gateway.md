# Defining the API Gateway

To expose our Lambda function to the internet so it can receive webhooks from the LINE Platform, we use Amazon API Gateway. This service acts as the public-facing endpoint for our bot.

## 1. The `apigw.LambdaRestApi` Construct

The AWS CDK provides a high-level L2 construct, `LambdaRestApi`, which makes it very simple to create an API Gateway that is fully integrated with a Lambda function.

This single construct automatically creates:

- A `RestApi` endpoint.
- A `Resource` (the path part of the URL).
- A `Method` (e.g., `POST`, `ANY`) for the resource.
- An `Integration` that connects the method to our Lambda function.
- The necessary permissions for API Gateway to invoke the Lambda function.

### Example from `lib/lambda-stack.ts`

```typescript
// lib/lambda-stack.ts
import * as apigw from 'aws-cdk-lib/aws-apigateway';

// ... (lambdaFunc is defined)

const api = new apigw.LambdaRestApi(this, 'Endpoint', {
  handler: lambdaFunc,
});
```

As you can see, the configuration is minimal. We simply instantiate `LambdaRestApi` and pass our `lambda.Function` construct to the `handler` property. The CDK handles the rest of the integration details.

By default, this creates a **proxy integration**. This means that any request to any path on the API Gateway will be forwarded ("proxied") to the Lambda function. The entire HTTP request (headers, body, path, etc.) is passed as the `event` object to the Lambda handler.

This is exactly what we need for the LINE webhook, which is a single `POST` request to a `/callback` URL.

## 2. Accessing the API URL

Once the stack is deployed, we need the public URL of the API Gateway to configure it in the LINE Developer Console as our "Webhook URL".

To make this easy, the stack defines a `CfnOutput`. This instructs CloudFormation to print the value of the API URL after a successful deployment.

### Example from `lib/lambda-stack.ts`

```typescript
// lib/lambda-stack.ts
import * as cdk from 'aws-cdk-lib';

// ... (api is defined)

new cdk.CfnOutput(this, 'ApiGatewayUrl', {
  value: api.url,
  description: 'API Gateway URL for the Line Echo Bot',
});
```

When you run `cdk deploy`, the output in your terminal will include a line similar to this:

```
Outputs:
EchoLineBotStack.ApiGatewayUrl = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/
```

This is the URL you will use for your LINE bot's webhook.
