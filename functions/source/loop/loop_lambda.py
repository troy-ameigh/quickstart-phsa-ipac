"""
Loop labmda function for IPAC-CLABSI
Purpose
-------
Read output.manifest, and save to csv file in source-csv for
triggering another job creation or send the file  to
aggregate folder depending on PR value
-----------------

* csv - tabular data with the patient information

------------------

outputmanifest schematics:

    output_manifest = {
       "comment":
       "table":{date1:{}, date2:{},...},
       "comment_on_pathogen"
       "bsi_type",
       "SourceTimelineImg",
       "source-ref"
       "iwp_plots":
       "category":{
          "caseInfo":{
             "comment":"
             },
             "new_comment":,
             "send_to_physician",
             "comment_on_pathogen",
             "pathogen""
          },
          "workerId":
          "source":
          }
       },
       "category-metadata":
       }
    }

"""
import os
import json
import urllib.parse
from io import StringIO
import boto3
import pandas as pd


def write_dataframe_to_csv_on_s3(dataframe, filename, bucket):
    """ Write a dataframe to a CSV on S3 """

    # Create buffer
    csv_buffer = StringIO()

    # Write dataframe to buffer
    dataframe.to_csv(csv_buffer, index=False)

    # Create S3 object
    s3_resource = boto3.resource("s3")

    # Write buffer to S3 object
    s3_resource.Object(
        bucket, f'{filename}').put(
        Body=csv_buffer.getvalue(), ServerSideEncryption="aws:kms")


def update_timeline(mrn):
    
    '''
    removes MRN that are completed from the timeline

    '''
    mrn = int(mrn)
    key = os.environ['CREATIONTIME_JOBS']
    bucket = os.environ['FEEDBACK_BUCKET']
    s3_client = boto3.client('s3')
    csv_obj = s3_client.get_object(Bucket=bucket, Key=key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    dataframe = pd.read_csv(StringIO(csv_string))
    print('update time line')
    i = dataframe.loc[dataframe['MRN'] == mrn].index
    dataframe = dataframe.drop(i)

    write_dataframe_to_csv_on_s3(dataframe, key, bucket)


def write_json_on_s3(bucket, object_path, data, dataframe):

    """
    Save json to a path
    """
    dataframe = dataframe.copy()
    # finding the decision from data object
    try:
        decision_dict = data['category']['caseInfo']['decision']
        for key in decision_dict:
            if decision_dict[key]:
                decision = key

        # if decision was not made and we will not increase review count,
        # PR is set in clabsi-production lamdba, its increased by 1.

        dataframe['decision'] = decision
        if 'PR' in dataframe.columns:
            dataframe.loc[:, 'PR'] = dataframe.loc[0, 'PR']
            dataframe['PR'] = dataframe['PR'].astype('int32')

        if decision == 'notsure':

            print('lowering pr by 1')
            if 'PR' in dataframe.columns:
                dataframe['PR'] -= 1
                if dataframe.loc[0, 'PR'] == 0:

                    dataframe['PR'] = 0

                if dataframe.loc[0, 'PR'] == -1:
                    dataframe.drop(columns='PR', inplace=True)
        worker_id = data['category']['workerId']
        if 'PR' in dataframe.columns:
            if dataframe['PR'][0] >= 1:
                dataframe['second_reviewer_id'] = worker_id
            else:
                dataframe['first_reviewer_id'] = worker_id

        job_creation_date = data['category-metadata']['creation-date']
        dataframe['job_creation_date'] = job_creation_date
        # setting send_to_physician column
        #  in dataframe according to dataManifest
        if "send_to_physician" in data[
                'category']['caseInfo']:
            dataframe['send_to_physician'] = data[
                'category']['caseInfo']['send_to_physician']
        if "BSI_type" in data['category']['caseInfo']:
            bsi_type_dict = data['category']['caseInfo']['bsi_type']
            bsi_type = ''
            for key in bsi_type_dict:
                if bsi_type_dict[key]:
                    bsi_type = key
                    dataframe['BSI_type'] = bsi_type

            # Blood Stream Infection subtype, if any specified
            if bsi_type == 'LCBI 1' and data[
                'category']['caseInfo'][
                    'MBI_LCBI_1']['MBI-LCBI 1']:
                dataframe['BSI_subtype'] = 'MBI LCBI 1'
            elif bsi_type == 'LCBI 2' and data[
                'category']['caseInfo'][
                    'MBI_LCBI_2']['MBI-LCBI 2']:
                dataframe['BSI_subtype'] = 'MBI LCBI 2'
            elif bsi_type == 'LCBI 3' and data[
                'category']['caseInfo'][
                    'MBI_LCBI_3']['MBI-LCBI 3']:
                dataframe['BSI_subtype'] = 'MBI LCBI 3'

        if "commonnocasereason" in data['category']['caseInfo']:
            nocasereason = ''
            if data['category']['caseInfo']['commonnocasereason']['RIT']:
                nocasereason = 'RIT'
            elif data['category']['caseInfo']['commonnocasereason']['POA']:
                nocasereason = 'POA'
            elif data['category']['caseInfo'][
                    'commonnocasereason']['Common excluded pathogen']:
                nocasereason = 'Common excluded pathogen'
            dataframe['commonnocasereason'] = nocasereason

        if 'alternate_diagnosis' in data[
                'category']['caseInfo']:
            dataframe['alternate_diagnosis'] = data[
                'category']['caseInfo']['alternate_diagnosis']

        if "comment_on_pathogen" in data[
                'category']['caseInfo']:
            comment_on_pathogen = data[
                'category']['caseInfo']['comment_on_pathogen']
            dataframe['comment_on_pathogen'] = comment_on_pathogen

    except KeyError:
        print("output.manifest format problem: keyError problem")

    try:
        if 'pathogen' in data["category"]['caseInfo']:
            dataframe['pathogen'] = data[
                "category"]['caseInfo']['pathogen']
        if 'other_pathogen' in data["category"]['caseInfo']:
            dataframe['other_pathogen'] = data[
                "category"]['caseInfo']['other_pathogen']
        # concating all the comments so we dont lose the previous comments
        if 'comment' in data['category']['caseInfo']:
            if 'new_comment' in data['category'][
                'caseInfo']:
                dataframe['comment'] = " ".join(
                    [data['category']['caseInfo']['comment'],
                     "----", data['category']['caseInfo']['new_comment']])
            else:
                dataframe['comment'] = data['category'][
                    'caseInfo']['comment']
        if 'new_comment' in data['category']['caseInfo']:
            if 'comment' not in data['category']['caseInfo']:
                dataframe['comment'] = data['category'][
                    'caseInfo']['new_comment']

        # adding IWP_comments to the dataframe

        if "IWP_comment" in data['category']['caseInfo']:

            iwp_comment = data['category']['caseInfo']['IWP_comment']

            dataframe['IWP_comment'] = iwp_comment

    except KeyError:
        print('output.manifest format problem,\
            ["category"]["caseInfo"]["category"]\
                ["comment"] does not exists for comment')

    # writing to dataframe
    write_dataframe_to_csv_on_s3(dataframe,
                                 filename=object_path, bucket=bucket)

    return dataframe


def write_csv_aggregate(bucket, dataframe,
                        month, year, patient):
    ''' writes csv to augmented reporting folder for the final review
    '''
    print(f'patient  mrn {patient}')
    print('write_csv_aggregate is triggered')

    dataframe['mrn'] = patient
    if "MRN" in dataframe.columns:
        dataframe.drop(columns='MRN', inplace=True)
    client = boto3.client('s3')
    # setting up the final reporting file name scheme
    aggregate_filename = f'for_reporting_augmented/{year}/{month}.csv'
    try:
        # incase the aggregate file name already exist,
        # this will read the file, and add the csv to its body
        # reading the aggregate file object
        aggregate_file = client.get_object(
            Bucket=bucket, Key=aggregate_filename)
        # parsing it
        body = aggregate_file['Body']
        # decodig it
        csv_string = body.read().decode('utf-8')
        # convertingit to csv
        df_aggregate = pd.read_csv(StringIO(csv_string))
        # making a list of aggregate dataframe and new dataframe
        df_list = [df_aggregate, dataframe]
        # concating to create total df aggregate
        df_aggregate = pd.concat(df_list)

        write_dataframe_to_csv_on_s3(
            df_aggregate, aggregate_filename, bucket)
        print('writing to aggregate finished')
    except Exception:
        # incase the the file did not exist
        # setting df_aggregate to equal to our file
        df_aggregate = dataframe.copy()
        write_dataframe_to_csv_on_s3(
            df_aggregate, aggregate_filename, bucket)


def lambda_handler(event, context):
    """
    This function is called every time an output.manifest is generated.

    It reads in the output manifest file and depending the review selection,
    either feed the data back for labelling or push the information for
    reporting.
    """
    print(context)
    s3_client = boto3.client('s3')
    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    event_time = event['Records'][0]['eventTime']
    year = event_time.split("-")[0]
    month = event_time.split("-")[1]

    # Load the output manifest
    key = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    # filename = os.path.basename(key)

    # Read ['category-metadata']['job-name']in the output.manifest data
    output_manifest_object = s3_client.get_object(Bucket=bucket, Key=key)
    output_manifest_body = output_manifest_object['Body']
    manifest_data = json.loads(
        output_manifest_body.read().decode('utf-8'))

    # Output manifest contains information about the input csv
    if 'csv_bucket' in manifest_data and 'csv_path' in manifest_data:
        print(
            'Loading input csv datafile',
            manifest_data['csv_bucket'],
            manifest_data['csv_path'])
        # read csv file
        csv_obj = s3_client.get_object(
            Bucket=manifest_data['csv_bucket'],
            Key=manifest_data['csv_path'],
        )
        body = csv_obj['Body']
        dataframe = pd.read_csv(StringIO(body.read().decode('utf-8')))

    # finding patient MRN
    patient = manifest_data['mrn']
    # figure out the PR
    previously_reviewed = manifest_data['pr']
    dataframe['PR'] = previously_reviewed
    # extracing decision
    if 'category' in manifest_data:
        decision_dict = manifest_data['category']['caseInfo']['decision']
        # dummy variable
        name = 'none'
        for key in decision_dict:
            if decision_dict[key]:
                decision = key
        # Data to put for another round of review
        feedback_path = '{}/{}.csv'.format(
            os.environ['FEEDBACK_FOLDER'],
            patient,
        )

        # Outgoing data for reporting
        reporting_path = '{}/{}.csv'.format(
            os.environ['REPORTING_FOLDER'],
            patient,
        )

        # finding the name of ICP or physician to send the job next
        if "send_to_physician" in manifest_data['category']['caseInfo']:
            name = manifest_data[
                'category']['caseInfo'][
                    'send_to_physician']

        if decision.lower().startswith('case'):
            # at least 1 review by ICP and physician has been done

            if int(previously_reviewed) >= 1:
                if name in ["none", "", "Do not send notification"]:
                    # Push data for reporting
                    dataframe = write_json_on_s3(
                        os.environ['REPORTING_BUCKET'],
                        reporting_path,
                        manifest_data,
                        dataframe,
                    )
                    write_csv_aggregate(bucket, dataframe,
                                        month, year, patient)
                    update_timeline(patient)

                else:
                    dataframe = write_json_on_s3(
                        os.environ['FEEDBACK_BUCKET'],
                        feedback_path,
                        manifest_data,
                        dataframe,
                    )
            else:

                dataframe = write_json_on_s3(
                    os.environ['FEEDBACK_BUCKET'],
                    feedback_path,
                    manifest_data,
                    dataframe,
                )

        # if decision is not sure, we remake the job,
        # but keep the progress by rewriting source-csv
        elif decision.lower().startswith('notsure'):
            # Circlate data for another round of review
            dataframe = write_json_on_s3(
                os.environ['FEEDBACK_BUCKET'],
                feedback_path,
                manifest_data,
                dataframe,
            )
        else:
            # Decision "no case"
            # at least 1 review by ICP and physician has been done
            if int(previously_reviewed) >= 1:

                if name in ["none", "", "Do not send notification"]:

                    # Push data for reporting
                    dataframe = write_json_on_s3(
                        os.environ['REPORTING_BUCKET'],
                        reporting_path,
                        manifest_data,
                        dataframe,
                    )
                    # writing data to aggregate folder
                    write_csv_aggregate(bucket, dataframe, month, year,
                                        patient)

                    update_timeline(patient)

                else:

                    write_json_on_s3(
                        os.environ['FEEDBACK_BUCKET'],
                        feedback_path,
                        manifest_data,
                        dataframe,
                    )

            else:
                # sending the job back to source-csv
                # to be reviewed by a physician
                write_json_on_s3(
                    os.environ['FEEDBACK_BUCKET'],
                    feedback_path,
                    manifest_data,
                    dataframe,
                )

        print("Decision was:", decision)
