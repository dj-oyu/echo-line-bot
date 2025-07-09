# AWS CDK: Core Concepts

The AWS CDK has a few core concepts that are essential to understand. They provide a hierarchy for organizing and deploying your AWS resources.

## The Construct Tree

The entire CDK application is a hierarchy of **Constructs**, known as the construct tree.

- The **App** is the root of the tree.
- **Stacks** are children of the App.
- **Resources** (and other constructs) are children of Stacks.

```
App
└── MyBotStack (Stack)
    ├── MyLambdaRole (IAM Role Resource)
    ├── MyLambdaFunction (Lambda Function Resource)
    └── MyApiGateway (API Gateway Resource)
```

---

## 1. Constructs

**Constructs are the basic building blocks of the CDK.** A construct can represent a single AWS resource (like an S3 bucket) or it can be a higher-level component that encapsulates multiple related resources.

When you instantiate a construct, you always pass three parameters: `scope`, `id`, and `props`.

- **`scope`**: Tells the construct where it belongs in the construct tree. For a resource, the scope is almost always `this` (referring to the Stack it's in).
- **`id`**: A locally unique identifier for the construct within its scope. The CDK uses this ID to generate unique CloudFormation resource names.
- **`props`**: A set of properties or parameters used to configure the construct. These correspond to the resource's configuration settings.

### Levels of Constructs

- **L1 (Level 1)**: Direct, one-to-one mappings to CloudFormation resources (e.g., `CfnBucket`). They are verbose and require full configuration.
- **L2 (Level 2)**: Curated, high-level constructs (e.g., `s3.Bucket`). These are the standard constructs you will use most of the time. They provide sensible defaults, helper methods, and reduce boilerplate.
- **L3 (Level 3) / Patterns**: The highest-level constructs, often encapsulating an entire architectural pattern (e.g., a Fargate service with a load balancer). This project uses L2 constructs.

---

## 2. Stacks

**A Stack is the unit of deployment in the CDK.** All the resources defined within a stack are provisioned and managed as a single unit. A CDK Stack maps directly to an AWS CloudFormation Stack.

In our project, we define our stacks as classes that extend the `cdk.Stack` class. The constructor of this class is where we define all the resources (constructs) that belong to the stack.

```typescript
// lib/cdk-stack.ts
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

export class MyBotStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // The 'scope' for these resources is 'this' (the Stack)
    const myFunction = new lambda.Function(this, 'MyLambda', { /* ... props ... */ });
    const myRole = new iam.Role(this, 'MyRole', { /* ... props ... */ });
  }
}
```

---

## 3. App

**The App is the root of the construct tree and the entrypoint for your CDK application.** It acts as a container for all the stacks you define.

The App object is instantiated in `bin/cdk.ts`. This is where you create instances of your stack classes.

```typescript
// bin/cdk.ts
#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { MyBotStack } from '../lib/cdk-stack';

const app = new cdk.App(); // The App is the root

// Instantiate the stack
new MyBotStack(app, 'EchoLineBotStack', {
  /* ... props ... */
});
```

You can define multiple stacks within a single App, which allows you to manage different parts of your application lifecycle independently (e.g., a database stack and an application stack).
