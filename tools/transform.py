#******************************************************************************
 #  Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved. 
 #  Licensed under the Apache License Version 2.0 (the 'License'). You may not
 #  use this file except in compliance with the License. A copy of the License
 #  is located at                                                            
 #                                                                              
 #      http://www.apache.org/licenses/                                        
 #  or in the 'license' file accompanying this file. This file is distributed on
 #  an 'AS IS' BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or
 #  implied. See the License for the specific language governing permissions and
 #  limitations under the License.                                              
#******************************************************************************/

import json
import argparse
from collections import OrderedDict


def transform_template(template, save_path, lambda_zip_key, lambda_jar_key):
    with open(template) as json_file:
        data = json.load(json_file, object_pairs_hook=OrderedDict)
        resources = data.get("Resources")
        keys = set(resources.keys())
        for key in keys:
            if key.endswith("LogGroup") and not key.startswith("ApiGateway") and not key.startswith("ApiAccess"):
                name = key.replace("LogGroup", "")
                lambda_logical_id = key.replace("LogGroup", "LambdaFunction")
                # Remove all the logGroups generated by the Serverless Framework
                del resources[key]

                # Remove the function name for the lambda so it could be auto generated
                print("Function name: " + resources[lambda_logical_id]["Properties"]["FunctionName"])
                del resources[lambda_logical_id]["Properties"]["FunctionName"]
                resources[lambda_logical_id]["DependsOn"].remove(name + "LogGroup")

                # Replace all the lambda zip locations
                s3key = resources[lambda_logical_id]["Properties"]["Code"]["S3Key"]
                if s3key.endswith("zip"):
                    resources[lambda_logical_id]["Properties"]["Code"]["S3Key"] = lambda_zip_key
                elif s3key.endswith("jar"):
                    resources[lambda_logical_id]["Properties"]["Code"]["S3Key"] = lambda_jar_key

            # Remove and update any named resources
            if key == "IamRoleLambdaExecution":
                del resources[key]["Properties"]["RoleName"]
                resources[key]["Metadata"] = {
                    "cfn_nag": {
                        "rules_to_suppress": [
                            { "id": "W11", "reason": "Used to send emails to any email address" }
                        ]
                    }
                }

            if key == "AuthorizerApiGatewayAuthorizer":
                resources[key]["Properties"]["Name"] = {
                    "Fn::Join": ["", [{"Ref": "AWS::StackName"}, "-", "authorizer"]]
                }

            if key.endswith("LambdaFunction"):
                # Add CFN_NAG related metadata for all lambda functions
                resources[key]["Metadata"] = {
                    "cfn_nag": {
                        "rules_to_suppress": [
                            { "id": "W89", "reason": "Lambda functions will not be deployed inside a VPC for now" },
                            { "id": "W92", "reason": "Lambda functions will not define ReservedConcurrentExecutions to reserve simultaneous executions for now" }
                        ]
                    }
                }
                if "Description" in resources[key]["Properties"]:
                    resources[key]["Properties"]["Description"] = resources[key]["Properties"]["Description"].replace("\n", "")

                if key == "KvsProcessRecordingLambdaFunction":
                    resources[key]["Properties"]["Code"] = {
                        "S3Bucket": {
                                "Ref": "ServerlessDeploymentBucket"
                        },
                        "S3Key": lambda_jar_key,
                        "S3ObjectVersion": {
                                "Ref": "LambdaDeploymentJarPackageVersion"
                        }
                    }
                else:
                    resources[key]["Properties"]["Code"] = {
                        "S3Bucket": {
                                "Ref": "ServerlessDeploymentBucket"
                        },
                        "S3Key": lambda_zip_key,
                        "S3ObjectVersion": {
                                "Ref": "LambdaDeploymentZipPackageVersion"
                        }
                    }

            if key == "ApiGatewayRestApi":
                resources[key]["Properties"]["Name"] = {
                    "Fn::Join": ["", [{"Ref": "AWS::StackName"}, "-", "api"]]
                }

            if key.startswith("ContactVoicemailStreamIamRole"):
                resources[key]["Metadata"] = {
                    "cfn_nag": {
                        "rules_to_suppress": [
                            { "id": "W21", "reason": "NotResource needed to send SMS from SNS." },
                            { "id": "W11", "reason": "Must allow all resources for transcribe." },
                            { "id": "W76", "reason": "IAM policy needs the verbosity." }
                        ]
                    }
                }
            if key.startswith("ApiAccessLogGroup"):
                resources[key]["Metadata"] = {
                    "cfn_nag": {
                        "rules_to_suppress": [
                            { "id": "W84", "reason": "CloudWatchLogs LogGroup will not specify a KMS Key Id to encrypt the log data for now." },
                            { "id": "W86", "reason": "CloudWatchLogs LogGroup will not specify RetentionInDays to expire the log data for now." },
                        ]
                    }
                }
            if key.startswith("KvsProcessRecordingIamRole"):
                resources[key]["Metadata"] = {
                    "cfn_nag": {
                        "rules_to_suppress": [
                            { "id": "W11", "reason": "Must allow all resources for kinesis video streams." }
                        ]
                    }
                }

            if key.startswith("ApiGatewayDeployment"):
                resources[key]["Metadata"] = {
                    "cfn_nag": {
                        "rules_to_suppress": [
                            { "id": "W45", "reason": "Updating this field prevents stack updates." }
                        ]
                    }
                }

            if key.endswith("Options"):
                resources[key]["Metadata"] = {
                    "cfn_nag": {
                        "rules_to_suppress": [
                            { "id": "W59", "reason": "Options method cannot have an authorizer." }
                        ]
                    }
                }

        resources["AudioRecordingsBucketReadPolicy"] = {
            "Type" : "AWS::S3::BucketPolicy",
            "Properties" : {
                "Bucket" : {"Ref": "AudioRecordingsBucket"},
                "PolicyDocument": {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "AWS": {"Ref": "AWS::AccountId"}
                            },
                            "Action": "s3:GetObject",
                            "Resource": {
                                "Fn::Sub": "arn:aws:s3:::${AudioRecordingsBucket}/*"
                            }
                        },
                        {
                            "Effect": "Deny",
                            "Principal": "*",
                            "Action": "s3:*",
                            "Resource": {
                                "Fn::Sub": "arn:aws:s3:::${AudioRecordingsBucket}/*"
                            },
                            "Condition": {
                                "Bool": {
                                    "aws:SecureTransport": "false"
                                }
                            }
                        }
                    ]
                }
            }
        }

        del resources["ServerlessDeploymentBucketPolicy"]
        del resources["ServerlessDeploymentBucket"]


        data["Parameters"]["ServerlessDeploymentBucket"] = {
            "Type": "String",
            "Default": "",
            "Description": "The bucket to which the lambda zips are deployed to"
        }

        data["Parameters"]["LambdaDeploymentJarPackageVersion"] = {
            "Type": "String",
            "Default": "",
            "Description": "S3 Object Version of the Lambda Deployment Jar Package"
        }

        data["Parameters"]["LambdaDeploymentZipPackageVersion"] = {
            "Type": "String",
            "Default": "",
            "Description": "S3 Object Version of the Lambda Deployment Zip Package"
        }

        with open(save_path, 'w') as outfile:
            json.dump(data, outfile, indent=2, sort_keys=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--template', help='Path to Serverless Cloudformation Template')
    parser.add_argument('--save', help='Path to save')
    parser.add_argument('--zip', help='Zip Key Path')
    parser.add_argument('--jar', help='Jar Key Path')
    args = parser.parse_args()

    transform_template(args.template, args.save, args.zip, args.jar)