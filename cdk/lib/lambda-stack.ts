import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as path from 'path';

export class LineEchoStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const lambdaFunc = new lambda.Function(this, 'lineEchoBot', {
      runtime: lambda.Runtime.PYTHON_3_11,  // 適宜バージョンを選択
      handler: 'main.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../')), // main.pyの場所
    });

    new apigw.LambdaRestApi(this, 'Endpoint', {
      handler: lambdaFunc,
    });
  }
}
