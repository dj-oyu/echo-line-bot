# Defining the Lambda Function

This project defines the AWS Lambda function using the standard `aws-cdk-lib/aws-lambda` module. This document explains how the function is defined in `lib/lambda-stack.ts`.

## 1. The `lambda.Function` Construct

This is the core L2 construct for defining a Lambda function. It requires several key properties:

```typescript
// lib/lambda-stack.ts

const lambdaFunc = new lambda.Function(this, 'lineEchoBot', {
  runtime: lambda.Runtime.PYTHON_3_11,
  handler: 'main.lambda_handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
  layers: [lineBotLayer],
  environment: {
    CHANNEL_SECRET: process.env.CHANNEL_SECRET || '',
    CHANNEL_ACCESS_TOKEN: process.env.CHANNEL_ACCESS_TOKEN || '',
  },
});
```

- **`runtime`**: Specifies the execution environment. We use `lambda.Runtime.PYTHON_3_11` for our Python code.
- **`handler`**: The entrypoint for the function. It's in the format `file_name.function_name`. Here, it points to the `lambda_handler` function inside the `main.py` file.
- **`code`**: Defines where the Lambda function's source code is located. `lambda.Code.fromAsset()` tells the CDK to package the contents of the specified directory (`lambda/` at the project root) and upload it.
- **`layers`**: A list of Lambda Layers to attach to the function. We use this for our dependencies (see below).
- **`environment`**: A key-value map of environment variables to make available to the function at runtime. We use this to pass the LINE channel credentials securely.

## 2. Managing Dependencies with Lambda Layers

To keep the main function code clean and to manage dependencies efficiently, this project uses a **Lambda Layer** for the `line-bot-sdk`.

A Lambda Layer is a separate zip archive that can contain libraries, custom runtimes, or other dependencies. You can share layers across multiple Lambda functions.

### `lambda.LayerVersion`

We define the layer using the `lambda.LayerVersion` construct:

```typescript
// lib/lambda-stack.ts

const lineBotLayer = new lambda.LayerVersion(this, 'LineBotLayer', {
  compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
  description: 'Layer for line-bot-sdk',
  code: lambda.Code.fromAsset(resolve(__dirname), {
    bundling: {
      image: lambda.Runtime.PYTHON_3_11.bundlingImage,
      command: [
        'bash', '-c',
        [
          'mkdir -p /asset-output/python',
          'pip install line-bot-sdk -t /asset-output/python',
        ].join(' && ')
      ]
    }
  })
});
```

- **`code`**: The most important part. We use `lambda.Code.fromAsset()` with a `bundling` option.
- **`bundling`**: This tells the CDK to run a Docker container locally to build the layer. The `command` installs the `line-bot-sdk` into the `python` directory of the asset output, which is the standard structure for Python layers.
- **`compatibleRuntimes`**: Specifies which runtimes this layer can be used with.

By using a layer, the main `lambda/` directory only needs to contain our application logic (`main.py`), not all its dependencies. This simplifies deployment and development.

## 3. Environment Variables

The Lambda function gets its channel credentials from environment variables defined in the stack. The CDK reads these values from a `.env.local` file at the project root using the `dotenv` library and injects them into the `lambda.Function` construct.

This is a secure way to manage secrets, as they are not hardcoded in the source code.
