'''
Sagemaker groundtruth can only keep the jobs alive for 10 days.
 This is our workaround solution.
We update a list everytime a job is created with its creation date.
If the current time and creation time are larger than 10 days then
this lambda will trigger job creation lambda by reading and
 reposting the patient file in the source-csv.
This will conserve the previous comments or
 review numbers made by the infection control or the physicians.

'''
import os
import time
import json
from datetime import date
from io import StringIO
import pandas as pd
import boto3


def write_dataframe_to_csv_on_s3(dataframe, filename, bucket):
    """ Write a dataframe to a CSV on S3 """

    # Create buffer
    csv_buffer = StringIO()

    # Write dataframe to buffer
    dataframe.to_csv(csv_buffer, index=False)

    # Create S3 object
    s3_resource = boto3.resource("s3")

    # Write buffer to S3 object
    s3_resource.Object(bucket, f'{filename}').put(
        Body=csv_buffer.getvalue(), ServerSideEncryption="aws:kms")


def check_creationtimefile():
    """
    Creates an 2 list of MRN and PRs.Checks the rows of  FileTime.csv
    If the difference of creation_time and current_time is larger than 10 days,
    it will add MRN and PR them to MRNS and PRS list

    ----------

    Returns
    -------
    list
    """

    key = os.environ['CREATIONTIME_JOBS']
    bucket = os.environ['FEEDBACK_BUCKET']

    s3_client = boto3.client('s3')
    csv_obj = s3_client.get_object(Bucket=bucket, Key=key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    dataframe = pd.read_csv(StringIO(csv_string))
    mrns = []
    prs = []

    # getting the current local time
    current_time = time.localtime(time.time())
    # converting to time stamp
    timestamp = time.mktime(current_time)
    # getting the date from time stamp
    my_date = date.fromtimestamp(timestamp)
    for i in dataframe.index:

        # getting the date from creation_time
        creation_time = pd.Timestamp(
            pd.to_datetime(dataframe.loc[
                i, 'CreationTime'])).to_pydatetime().date()

        # finding the number of days difference between
        #  current time and creation time
        time_diff = (my_date - creation_time).days
        # if the time difference is larger than 10 days
        if time_diff > 9:
            mrns.append(dataframe.loc[i, 'MRN'])
            prs.append(dataframe.loc[i, 'PR'])
    return mrns, prs


def removerow_creationtime(mrn, previously_reviewed):
    '''
    Given an MRN and PR it will remove
    those rows from from os.environ['CREATIONTIME_JOBS'] file.

    '''
    key = os.environ['CREATIONTIME_JOBS']
    bucket = os.environ['FEEDBACK_BUCKET']

    s3_client = boto3.client('s3')
    mrn = int(float(mrn))

    # getting file object
    csv_obj = s3_client.get_object(Bucket=bucket, Key=key)
    # extracting the csv
    body = csv_obj['Body']
    # reading and decodying the csv by utf-8
    csv_string = body.read().decode('utf-8')
    # converting csv to stringIO and pandas dataframe
    dataframe = pd.read_csv(StringIO(csv_string))
    # finding the rows tha have matching MRN and PR
    indexnames = dataframe[
        (dataframe['MRN'] == mrn) & (
            dataframe['PR'] == previously_reviewed)].index
    print('indexnames', indexnames)

    # removing rows in the indexnames
    dataframe.drop(indexnames, inplace=True)
    # rewritng the dataframe to s3
    write_dataframe_to_csv_on_s3(dataframe, key, bucket)
    print('removed fileTime')


def lambda_handler(event, context):
    '''
    This lambda is triggered using Cron job
    every 1 minutes (EventBridge CloudWatch Event).
    It requires S3 read/write access to "Production Bucket"

    '''
    print(context)
    print(event)
    # finding MRNs with creation days older than  10 days
    mrns, prs = check_creationtimefile()
    s3_client = boto3.client('s3')

    for i, _ in enumerate(mrns):
        mrn = mrns[i]
        previously_reviewed = prs[i]
        print(mrn)
        bucket = os.environ['FEEDBACK_BUCKET']

        # reading the patient file from source-csv
        key = f'source-csv/{mrn}.csv'
        csv_obj = s3_client.get_object(Bucket=bucket, Key=key)

        body = csv_obj['Body']
        csv_string = body.read().decode('utf-8')
        dataframe = pd.read_csv(StringIO(csv_string))
        # writing the file back to s3 , inorder to trigger job creation lambda
        write_dataframe_to_csv_on_s3(dataframe, key, bucket)
        # removing that MRN and PR from timeline.csv file
        removerow_creationtime(mrn, previously_reviewed)
        print('rewrote to csv')

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
