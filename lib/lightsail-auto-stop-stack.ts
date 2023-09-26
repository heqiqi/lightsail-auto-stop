import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Effect } from 'aws-cdk-lib/aws-iam';
import { CfnOutput } from 'aws-cdk-lib';

export class LightsailAutoStopStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    // create sns for notification
    const snsTopic = new sns.Topic(this, 'Lightsail-quota-notificatoin');

    const lambdaExecuteRole = new iam.Role(this, 'lightsail-execute-role', {
      assumedBy: new iam.CompositePrincipal(new iam.ServicePrincipal("lambda.amazonaws.com")),
      
    });

    lambdaExecuteRole.addToPolicy(
      new iam.PolicyStatement({
        effect: Effect.ALLOW,
        resources: ['*'],
        actions: [            
          'lightsail:GetInstanceMetricData',
          'lightsail:GetInstance',
          'lightsail:StopInstance',
          'lightsail:GetInstances'
        ]
      })
    );

    const LightSailDtoMonitorLambda = new lambda.Function(this, 'Lightsail-dto-monitor', {
      runtime: lambda.Runtime.PYTHON_3_11,    // execution environment
      code: lambda.Code.fromAsset('lambda'),  // code loaded from "lambda" directory
      handler: 'lightsail-dto-monitor.lambda_handler',
      memorySize: 1024,
      timeout: cdk.Duration.seconds(300),
      role: lambdaExecuteRole,
      environment: {
        SNS_TOPIC: snsTopic.topicArn
      }
    });

    snsTopic.grantPublish(LightSailDtoMonitorLambda);

    new events.Rule(this, 'monitor-lightsail-cronjob', {
      schedule: events.Schedule.cron({ minute: '0' }), // Trigger  every min
      targets: [new targets.LambdaFunction(LightSailDtoMonitorLambda)],
    });

    new CfnOutput(this, 'LambdaFunc', { value: LightSailDtoMonitorLambda.functionArn });
    new CfnOutput(this, 'SNSTopic', { value: snsTopic.topicName });

  }
}
