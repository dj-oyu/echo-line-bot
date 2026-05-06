import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

/**
 * Default CDK Stack
 * 
 * This is the default CDK stack template. The actual LINE bot infrastructure
 * is defined in the LineEchoStack class in lambda-stack.ts.
 * 
 * @deprecated Use LineEchoStack instead for the LINE bot infrastructure
 */
export class CdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // This stack is currently unused. The actual LINE bot infrastructure
    // is defined in the LineEchoStack class in lambda-stack.ts.
    // 
    // If you need to add additional resources, consider adding them to
    // the LineEchoStack or creating a new stack that extends this one.
  }
}
