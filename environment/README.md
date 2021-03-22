# PHC IPAC


## Components

### Infrastructure
- AWS CloudFormation for setting up the components required by the pipeline
- AWS IAM for assigning required permissions

### Pipeline
- AWS CodeCommit for source code repository
- AWS CodePipeline for orchestration
- AWS CodeBuild for building and packaging the application
- AWS CodeDeploy for publising the built artifacts to an environment
- AWS EventBridge to initiate the pipeline every time changes are pushed to the repository

## Overview of the Solution

Solution consist of a source code repository hosted in AWS CodeCommit. When changes are pushed to the repositoty, an event will be fired with an AWS CodePipeline as target. The pipeline is composed of three stages: source, build and deploy.

- Source: The source stage will make the commit available for the next stage: build
- Build: The build stage is implemented by AWS CodeBuild actions to build the source code and produce artifacs to be used by the next stage: deploy
- Deploy: In the deploy stage, implemented by AWS CodeDeploy, the artifacts produced by the previous stage will be published to the configured environment

## Usage

### Pre-requisites

- AWS Console or AWS CLI access with sufficient permissions to create CloudFormation stacks and the resources defined by the stack
- An existing CodeCommit repository with application source code
- CodeBuild appspec.yaml file present in the application source code repository
- CodeDeplot deployspec.yaml file present in the application source code repository

### Parameters

|Parameter|Accepted Values|Description|
|---------|---------------|-----------|
|ApplicationName|String|Name of the application managed by this pipeline|
|DeploymentGroupName|String|Name of the Application Group managed by this piepline|
|RepositoryName|CodeCommit Repository Name|Name of a CodeCommit repository where the source code for this application exists|
|RepositoryBranchName|String|A valid branch in the application repository|
|PipelineName|String|Name of this pipeline|
|VpcId|||
|Environment|String|Name of this environment. All lower-case|

### Creating a new environment using AWS Console

### Creating a new environment using AWS CLI (.i.e. via automation)

1. Create a CloudFormation parameters file
1. Create the stack
   ```
   aws cloudformation create-stack --template-file file://pipeline.yaml --stack-name <stack name> --capabilities CAPABILITY_NAMED_IAM --parameters file://<parameters.json>
   ```

### Updating an existing environment using AWS Console

### Updating an existing environment using AWS CLI (.i.e. via automation)

1. Update the template with required changes
1. Deploy the stack
   ```
   aws cloudformation deploy --template-file file://pipeline.yaml --stack-name <stack name>
   ```

**NOTE:** If additional parameters are required by the template changes, or if an existing parameter value must change, provide them with
``` --parameters-override ParameterKey=<key name>,ParameterValue=<key value>``` where ```<key name>``` and ```<key value>``` are the respective key and value parameters.

### Update parameters.json

   -Update the parameters.json for lambda names, region, aws account, sagemaker label team arn, VPC id, and s3 names.


### Permissions required for the Job-creation lambda in-addition to role created by the CloudFormation deployment. 

	-AmazonSageMakerFullAccess (arn:aws:iam::aws:policy/AmazonSageMakerFullAccess)
	-AWSLambdaBasicExecutionRole  (arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole)
	-AmazonSageMakerGroundTruthExecution (arn:aws:iam::aws:policy/AmazonSageMakerGroundTruthExecution)
	- SES access :{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "ses:SendEmail",
            "Resource": "*"
        }
    ]
}

### Resources required By Lambda functions:
Preprocess lambda:
   Memory = 4096 MB
   timeout= 5 min
Job creation Lambda:
   Memory = 512 MB
   timeout= 5 min
Loop Lambda :
   Memory = 512 MB
   timeout = 5 min