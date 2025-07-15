#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { LineEchoStack } from '../lib/lambda-stack';

/**
 * CDK Application Entry Point
 * 
 * This file initializes the CDK application and creates the LineEchoStack
 * which contains all the infrastructure for the LINE bot.
 */
const app = new cdk.App();

// Create the LINE Echo Bot stack
new LineEchoStack(app, 'LineEchoStack', {
  description: 'LINE Echo Bot with AI processing capabilities',
  env: {
    // Use default account and region from CDK context
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});

// Synthesize the CloudFormation template
app.synth();
