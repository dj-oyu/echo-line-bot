# Using the AWS CDK CLI

The AWS CDK comes with a powerful command-line interface (CLI), `cdk`, which is the primary tool for interacting with your CDK application.

All commands should be run from within the `cdk/` directory of this project.

## Common Workflow

A typical development workflow involves the following sequence of commands:

1.  **`npm install`**: Before you do anything else, install the Node.js dependencies defined in `package.json`.
2.  **`cdk synth`**: After making changes to your stack definition in TypeScript, synthesize it to see the generated AWS CloudFormation template.
3.  **`cdk diff`**: Compare your changes against the currently deployed stack to understand the impact of your changes.
4.  **`cdk deploy`**: Deploy your changes to your AWS account.

---

## Detailed Command Reference

### `cdk bootstrap`

- **What it does**: Deploys the "CDK Toolkit stack" to your AWS account/region. This stack contains resources (like an S3 bucket for storing assets) that the CDK needs to perform deployments. 
- **When to use it**: You only need to run this **once per AWS account/region combination** you want to deploy to. If you are deploying to a new environment for the first time, you must run `cdk bootstrap`.

### `cdk synth`

- **What it does**: Synthesizes the CDK code into a standard AWS CloudFormation template and prints it to the console. This does not deploy anything.
- **Why it's useful**: It allows you to inspect the exact CloudFormation resources that the CDK will create from your code. It's a great way to verify your changes and understand how the CDK constructs map to underlying AWS resources.

### `cdk diff`

- **What it does**: Compares the CloudFormation template generated from your current code with the template of the stack that is already deployed in AWS.
- **Why it's useful**: It provides a summary of what resources will be **added, modified, or deleted** if you were to deploy. This is a critical safety check to ensure you are not making unintended changes, especially destructive ones.

### `cdk deploy`

- **What it does**: Deploys your stack to AWS. It first synthesizes the code, uploads any necessary assets (like the Lambda function code), and then creates or updates the CloudFormation stack.
- **Security**: If the deployment involves any changes to IAM policies or other security-sensitive resources, the CDK will prompt you for confirmation before proceeding. You can use the `--require-approval never` flag to disable this for non-interactive environments.

### `cdk destroy`

- **What it does**: Destroys a deployed stack, deleting all the resources that were created as part of it.
- **Why it's useful**: For cleaning up development or test environments to avoid incurring costs.

### `npm run build` & `npm run watch`

These are not `cdk` commands, but are essential for development.

- **`npm run build`**: Compiles your TypeScript (`.ts`) files into JavaScript (`.js`), which is what Node.js actually executes.
You must run this after any TypeScript changes before running `cdk` commands.
- **`npm run watch`**: A convenience script that runs the TypeScript compiler in watch mode. It will automatically re-compile your code whenever you save a `.ts` file.
