import * as cdk from 'aws-cdk-lib';
import { LineEchoStack } from '../lib/lambda-stack';

const app = new cdk.App();
new LineEchoStack(app, 'LineEchoStack');


