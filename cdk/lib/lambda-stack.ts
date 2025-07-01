import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as path from 'path';
import * as dotenv from 'dotenv';
import { randomUUID } from 'crypto';
import { resolve } from 'path';

// 環境変数の読み込み
dotenv.config({ path: path.join(__dirname, '../../.env.local') });

export class LineEchoStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Line bot layer
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

    const lambdaFunc = new lambda.Function(this, 'lineEchoBot', {
      runtime: lambda.Runtime.PYTHON_3_11,  // 適宜バージョンを選択
      handler: 'main.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      layers: [lineBotLayer],
      environment: {
        CHANNEL_SECRET: process.env.CHANNEL_SECRET || '',
        CHANNEL_ACCESS_TOKEN: process.env.CHANNEL_ACCESS_TOKEN || '',
      },
    });

    const api = new apigw.LambdaRestApi(this, 'Endpoint', {
      handler: lambdaFunc,
    });

    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: api.url,
      description: 'API Gateway URL for the Line Echo Bot',
    });
  }
}
