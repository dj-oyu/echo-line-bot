# AWS CDK for Infrastructure

This documentation provides a deep dive into the AWS Cloud Development Kit (CDK), which is used to define and provision the cloud infrastructure for this project.

## 1. Overview

The AWS CDK allows us to define our cloud resources using a familiar programming language (TypeScript in this case). This provides several advantages over manually configuring resources in the AWS Console or using static configuration files:

- **Infrastructure as Code**: Our infrastructure is version-controlled, reviewable, and repeatable.
- **High-Level Abstractions**: The CDK provides high-level components (Constructs) that automatically provision multiple underlying resources with sensible, secure defaults.
- **Developer Productivity**: We can use the same tools, language, and development practices for our infrastructure as we do for our application code.

In this project, the CDK code is located in the `cdk/` directory and is responsible for setting up everything the LINE bot's Lambda function needs to run.

## 2. Project Structure (`cdk/` directory)

- **`bin/cdk.ts`**: The entrypoint for the CDK application. It loads the stacks defined in the `lib/` directory.
- **`lib/cdk-stack.ts`**: The main stack definition file. This is where we compose the different infrastructure components.
- **`lib/lambda-stack.ts`**: A separate stack specifically for the Lambda function, which promotes better organization.
- **`package.json`**: Defines the Node.js dependencies, including `aws-cdk-lib` and other required modules.
- **`cdk.json`**: A configuration file that tells the CDK Toolkit how to run the application (e.g., `"app": "npx ts-node --prefer-ts-exts bin/cdk.ts"`).
- **`tsconfig.json`**: The TypeScript compiler configuration.

## 3. Prerequisites for Local Development

To work with the CDK code locally, you will need:

1.  **An AWS Account** with credentials configured locally.
2.  **Node.js** (check `cdk/package.json` for version compatibility).
3.  **AWS CDK Toolkit**: This is the command-line tool for interacting with the CDK. Install it globally:
    ```bash
    npm install -g aws-cdk
    ```

## 4. Essential Commands

All commands should be run from within the `cdk/` directory.

- `npm install`: Installs the necessary Node.js dependencies.
- `npm run build`: Compiles the TypeScript code.
- `cdk synth`: Synthesizes the CDK stack into a CloudFormation template.
- `cdk diff`: Compares the current stack definition with the deployed version.
- `cdk deploy`: Deploys the stack to your AWS account.

## Next Steps

- [**Core Concepts**](./core_concepts.md)
- [**Defining the Lambda Function**](./defining_lambda.md)
- [**Defining the API Gateway**](./defining_api_gateway.md)
- [**IAM Roles**](./iam_roles.md)
- [**CLI Usage**](./cli_usage.md)
