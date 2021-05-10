"""
     input_manifest = {
            'table': table,
            'comment': comment,
            'timeline_image': timeline_image,
            'iwp_plots': iwp_plots,
            'review_counter': review_counter,
            'source-ref': mrn_id,
            }
"""
import json
import urllib.parse
import os
import time
from io import StringIO
from datetime import date
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
import boto3

print('Job creation lambda function')


def convert(value):
    '''
    convert np.int64 to int

    '''
    if isinstance(value, np.int64):
        return int(value)
    raise TypeError


def get_table_fields():
    """
    This function defines the fields presented on the front end table.
    """
    fields = [
        ('name_first', 'Given name(s)'),
        ('name_last', 'Surname'),
        ('birth_date_id', 'Birthdate'),
        ('bc_phn', 'PHN'),
        ('mrn', 'MRN'),
        ('encntr_num', 'Encounter #'),
        ('organism', 'Organism'),
        ('nursing_unit_short_desc', 'Nursing unit'),
        ('beg_effective_dt_tm',
            'Icu admission dt-tm (at collection or before)'),
        ('end_effective_dt_tm',
            'Icu discharge dt-tm (at collection or before)'),
        ('facility_name_src', 'Facility at collection'),
        ('collection_dt_tm', 'Collection dt-tm'),
        ('encntr_type_desc_src_at_collection', 'Encounter type at collection'),
        ('admit_dt_tm', 'Current encounter admit dt-tm'),
        ('disch_dt_tm', 'Current encounter disch dt-tm'),
        ('disch_disp_desc_src', 'Discharge disposition'),
        ('clinical_event_code_desc_src', 'Lab test'),
        ('lab_result', 'Lab result'),
        ('loc_room_desc_src_at_collection', 'Room at collection'),
        ('loc_bed_desc_src_at_collection', 'Bed at collection'),
        ('med_service_desc_src_at_collection',
            'Medical service at collection'),
        ('nursing_unit_desc_at_collection', 'Nursing unit at collection'),
        ('nursing_unit_short_desc_at_collection',
            'Same as nursing unit at collection in short form'),
        ('result_interpretation_desc_src', 'Result interpretation'),
        ('specimen_type_desc_src', 'Speciment type'),
        ('doc_set_name_result', 'Doc_set_name_result'),
        ('first_activity_start_dt_tm', 'Date of catheter insertion'),
        ('last_activity_end_dt_tm', 'Date of catheter removal'),
        ('first_catheter_type_result', 'Catheter type'),
        ('first_dressing_type_result', 'Dressing type'),
        ('first_site_result', 'Body site of catheter insertion'),
        ('line_tube_drain_insertion_seq',
            'Line tube drain insersion sequence'),
    ]

    return fields


def map_pathogen_name_to_id(pathogen_name):
    """
    """
    mapping = {
        "Acinetobacter baumannii": "p00",
        "Baceroides fragilis": "p01",
        "Burkholderia cepacia": "p02",
        "Candida albicans": "p03",
        "Candida giabrata": "p04",
        "Candida parapsilosis": "p05",
        "Candida tropicalis": "p06",
        "Citrobacter diversus": "p07",
        "Citrobacter freundii": "p08",
        "Citrobacter koseri": "p09",
        "Clostridium difficile": "p10",
        "Enterobacter aerogenes": "p11",
        "Enterobacter cloacae": "p12",
        "Enterococcus faecalis": "p13",
        "Enterococcus faecium": "p14",
        "Escherichia coli": "p15",
        "Haemophilus influenzae": "p16",
        "Klebsiella oxytoca": "p17",
        "Klebsiella pneumoniae": "p18",
        "Moraxella catarrhalis": "p19",
        "Morganella morganii": "p20",
        "Proteaus mirabilis": "p21",
        "Pseudomonas aeruginosa": "p22",
        "Serratia marcescens": "p23",
        "Staphylococcus aureus (MSSA, MRSA)": "p24",
        "Staphylococcus auricularis": "p25",
        "Staphylococcus capitis ssp. capitis": "p26",
        "Staphylococcus capitis ssp. unspecified": "p27",
        "Staphylococcus coagulase negative": "p28",
        "Staphylococcus cohnii": "p29",
        "Staphylococcus epidermidis": "p30",
        "Staphylococcus gallinarum": "p31",
        "Staphylococcus haemolyticus": "p32",
        "Staphylococcus hominis": "p33",
        "Staphylococcus lentus": "p34",
        "Staphylococcus lugdenensis": "p35",
        "Staphylococcus saccharolyticus": "p36",
        "Staphylococcus saprophyticus": "p37",
        "Staphylococcus schleiferi": "p38",
        "Staphylococcus sciuri": "p39",
        "Staphylococcus simulans": "p40",
        "Staphylococcus warneri": "p41",
        "Staphylococcus xylosus": "p42",
        "Stenotrophomonas maltophilia": "p43",
        "Streptococcus group A (Streptococcus pyogenes)": "p44",
        "Streptococcus group B (Streptococcus agalactiae)": "p45",
        "Streptococcus group D (Sterptococcus bovis)": "p46",
        "Streptococcus pneumoniae (pneumococcus)": "p47",
        "Strepotcuccus viridans (includes angiosus, bovis, mitis, mutans, salivarius)": "p49",
        "Torulopsis glabrata (Candida glabrata)": "p48",
        "Other pathogen": "p50",
        }

    pathogen = pathogen_name
    if pathogen_name in mapping:
        pathogen = mapping[pathogen_name]

    return pathogen



def modify_template_content(template, tablekeys):
    """
    Ground Truth has limitation on the number of nested loops. Correct that.

    """
    section = '''
        <div class="card-body encounter-table {date}">
            <label>Information for blood collection on {date}</label>
            <div id="table" name="table" class="table-editable">
                <table class="table table-bordered table-responsive-md
                     table-striped text-left main-table">
                    <tbody>
                        $3 for field in task.input.table.{date} $4
                            <tr>
                                <td  class="text-left">$1 field[0] $2</td>
                                <td class="pt-3-half" name=$1 field[0] $2
                                 contenteditable="true">$1 field[1] $2</td>
                            </tr>
                        $3 endfor $4
                    </tbody>
                </table>
            </div>
        </div>
        '''
    html = ''
    for collection_date in tablekeys:
        html = ''.join((html, section.format(**{'date': collection_date})))

    html = html.replace('$3', '{%').replace('$4', '%}').\
        replace('$1', '{{').replace('$2', '}}')
    template = template.replace('@@table@@', html)

    return template


def handle_template(data_table, bucket, reference_template_path,
                    patient_template_path):
    """
    Handle all html template related changes.
    """
    # Read the reference template
    template_object = boto3.resource('s3').\
        Object(bucket, reference_template_path)
    template_content = template_object.get()['Body'].read().decode('utf-8')

    # Modify the template
    complete_template = modify_template_content(template_content,
                                                data_table.keys())

    # Save the new template
    s3object = boto3.resource('s3').Object(bucket, patient_template_path)
    s3object.put(
        Body=(complete_template.encode('UTF-8')),
        ServerSideEncryption="aws:kms",
    )

    # Return the complete template path
    return "s3://{}/{}".format(bucket, patient_template_path)


def write_dataframe_to_csv_on_s3(dataframe, filename, bucket):
    """ Write a dataframe to a CSV on S3 """

    # Create buffer
    csv_buffer = StringIO()

    # Write dataframe to buffer
    dataframe.to_csv(csv_buffer, index=False)

    # Create S3 object
    s3_resource = boto3.resource("s3")

    # Write buffer to S3 object
    s3_resource.Object(bucket, filename).put(
        Body=csv_buffer.getvalue(), ServerSideEncryption="aws:kms")


def write_timeline(mrn, previously_reviewed):
    '''
    writes patient MRN, PR and creationtime to JobCreationTime file,
    in order to track label job creation times

    '''
    key = os.environ['CREATIONTIME_JOBS']
    bucket = os.environ['PRODUCTION']
    source_csv = f's3://{bucket}/source-csv/{mrn}.csv'

    s3_client = boto3.client('s3')
    csv_obj = s3_client.get_object(Bucket=bucket, Key=key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    dataframe = pd.read_csv(StringIO(csv_string))

    current_time = time.localtime(time.time())
    timestamp = time.mktime(current_time)
    currenttime = date.fromtimestamp(timestamp)
    dictionary = {'MRN': mrn, 'PR': previously_reviewed,
                  'CreationTime': currenttime,
                  'SourceCSV': source_csv}
    dataframe = dataframe.append(dictionary, ignore_index=True)
    write_dataframe_to_csv_on_s3(dataframe, key, bucket)

    print('finished writing time line')


def get_table(dataframe):
    """
    Generate the tabular data for the input manitest file.
    Parameters
    ----------
    dataframe : pd.DataFrame
        One patient data from the csv.
    Returns
    -------
    table : dictionary
        key: encounter_date, value: {field_name: value}
    Format
    ------
    'table': {
        'encounter_date': {
            'field': 'value',
            },
        }
    Note
    ----
    Because of the payload limit of the input manifest file,
    the table size is restricted (max_record_number)
    """
    dataframe['collection_dt_tm'] = pd.to_datetime(
        dataframe['collection_dt_tm'])
    max_record_number = 11
    # Sort by collection dates
    dataframe.sort_values(['collection_dt_tm'], inplace=True)
    if len(dataframe) > max_record_number:
        dataframe = dataframe.loc[:max_record_number]
        dataframe.loc[max_record_number, :] = ""
        dataframe.loc[max_record_number, 'name_first'] = \
            'Patient has too many collection dates,\
            please check Cerner to for more details!'
    # Generate a label for collection count, if there are multiple collections
    # on the same day
    count = 0
    collection_date = ''
    for index in dataframe.index:
        if index < max_record_number - 1:
            print(f'index :{index}')
            print(dataframe['collection_dt_tm'])
            if collection_date == dataframe.loc[index, 'collection_dt_tm']:
                count += 1
            else:
                count = 1
            collection_date = dataframe.loc[index, 'collection_dt_tm']
            dataframe.loc[index, 'collection_count'] = \
                '{collection_date}_{number}'.format(
                    collection_date=pd.to_datetime(dataframe.loc[
                        index, 'collection_dt_tm']).strftime('%Y-%m-%d'),
                    number=count,
            )
        else:
            dataframe.loc[index, 'collection_count'] = "DateNotAvailable"

    dataframe = dataframe.set_index('collection_count')
    # Transform into a dictionary
    table_dict = dataframe.astype(str).T.to_dict()

    table = {}
    for collection_date in table_dict:
        table[collection_date] = []
        for fieldname, humanname in get_table_fields():
            try:
                table[collection_date].append(
                    [humanname, table_dict[collection_date][fieldname]]
                    )
            except KeyError:
                pass
    return table


def gen_data_dict(dataframe, bucket):
    """
    Generate input manifest content.
    """

    data = {}
    mrn_id = dataframe['mrn'][0]
    data['table'] = get_table(dataframe)
    extra_columns = [
        'comment_on_pathogen', 'BSI_type',
        'other_pathogen', 'pathogen',
        'commonnocasereason', 'IWP_comment',
        'alternate_diagnosis', 'decision']

    for column in extra_columns:
        if column in dataframe.columns:
            if column == 'pathogen':
                data[column] = map_pathogen_name_to_id(dataframe[column][0])
            else:
                data[column] = dataframe[column][0]

    if 'clabsi' in dataframe.columns:
        data['collection_class'] = []
        count = 0
        collection_date = ''
        for index in dataframe.index:

            if collection_date == dataframe.loc[index, 'collection_dt_tm']:
                count += 1
            else:
                count = 1
            collection_date = dataframe.loc[index, 'collection_dt_tm']

            collection_count = '{collection_date}_{number}'.format(
                collection_date=pd.to_datetime(dataframe.loc[
                    index, 'collection_dt_tm']).strftime('%Y-%m-%d'),
                number=count,
                )

            if str(dataframe.loc[index, 'clabsi']).lower() =='true':
                print('i passed true test!', dataframe.loc[index, 'clabsi'].astype(str))

                data['collection_class'].append((collection_count))

        print(data['collection_class'])
    if 'comment' in dataframe.columns:
        if str(dataframe['comment'][0]) not in [
                'None', '(Null)', 'nan', 'Non']:
            data['comment'] = str(dataframe['comment'][0])

    if 'new_comment' in dataframe.columns:
        if str(dataframe['new_comment'][0]) not in [
                'None', '(Null)', 'nan', 'Non']:
            data['comment'] = " ".join([data['comment'], "----", str(
                dataframe['new_comment'][0])])

    data['sourcetimelineimg'] = f's3://{bucket}/images/{mrn_id}/timeline.png'
    data['source-ref'] = str(mrn_id)

    # Listing all the plots existing under patient mrn folder in s3
    responses = boto3.client('s3').list_objects(
        Bucket=bucket,
        Delimiter=f'images/{mrn_id}/IWP/plots_',
        Prefix=f'images/{mrn_id}/IWP/plots_',
    )

    plot_list = []
    for response in responses['Contents']:
        plot_list.append(response['Key'])

    # Creating a list for Infection Window plots
    data['iwp_plots'] = {}
    plots = sorted(list(set(plot_list)))

    for index, collection_time in enumerate(
            sorted(list(data['table'].keys()))):
        data['iwp_plots'][collection_time] = f's3://{bucket}/{plots[index]}'

    print(data['iwp_plots'])

    return data


def lambda_handler(event, context):
    """
    Recieves event, by getting triggered with addition of
     files to s3://ipac-clabsi-production/source-csv/.
    Creates a input manifest file from the context of dataframe.
    Sends a request to sagemaker client for Label job creation.

    ----------
    fieldname : Event
        AWS Lambda uses this parameter to pass in event data to the handler.
        This parameter is usually of the Python dict type.
        It can also be list, str, int, float, or NoneType type.
        When you invoke your function,
        you determine the content and structure of the event.
        When an AWS service invokes your function,
        the event structure varies by service.
        For details, see Using AWS Lambda with other services.

    fieldname: context
        AWS Lambda uses this parameter to
         provide runtime information to your handler


    Returns
    -------
        Sagemaker labeling job status description
    """
    print(context)
    s3_client = boto3.client('s3')
    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'],
                                    encoding='utf-8')
    filename = os.path.basename(key)
    manifest_path = 'manifests/' + filename + '.manifest'
    mrn = filename.split(".")[0]

    try:
        # read csv file
        csv_obj = s3_client.get_object(Bucket=bucket, Key=key)
        body = csv_obj['Body']
        csv_string = body.read().decode('utf-8')

        # initialize the data dictionary
        # Grab the header and turn it into json
        dataframe = pd.read_csv(StringIO(csv_string))

        # Remove NaN from the dataframe, because json can not handle NaN
        dataframe.fillna('None', inplace=True)

        # tracking the number of previews reviews
        dataframe.drop(columns=[
            i for i in dataframe.columns if i[:3] == 'Unn'], inplace=True)
        # PR mean previously reviewed.
        # If this dataframe has been previously through the job creation
        # pipeline it will have the column PR
        # We will increase the value of PR by 1 to
        # track the number of times this case has been reviewed.

        if 'PR' in dataframe.columns:
            print('increasing pr by 1')
            dataframe.loc[:, 'PR'] += 1
        else:
            dataframe.loc[:, 'PR'] = 0
        previously_reviewed = dataframe['PR'].max()

        if 'mrn' in dataframe.columns:
            mrn_id = dataframe.mrn[0]
        if 'MRN' in dataframe.columns:
            mrn_id = dataframe.MRN[0]
        mrn_id = str(mrn_id)

        data = gen_data_dict(dataframe, bucket)

        data['csv_bucket'] = os.environ['PRODUCTION']
        data['csv_path'] = key
        data['pr'] = previously_reviewed
        data['mrn'] = mrn_id
        # Write our manifest file if going through groundstation
        s3write = boto3.resource('s3')
        s3object = s3write.Object(bucket, manifest_path)
        s3object.put(Body=(bytes(json.dumps(
            data, default=convert).encode('UTF-8'))),
            ServerSideEncryption="aws:kms")

        # Handle UI template
        complete_template_path_uri = "s3://{}/{}".format(
            os.environ['PRODUCTION'],
            os.environ['TEMPLATE_PATH'],
        )
        # Writing the patient MRN to CreationTime file,
        #  so it can be tracked, and relunched if expired.
        write_timeline(mrn_id, dataframe['PR'][0])
        if 'second_reviewer_id' in dataframe.columns:
            worker_id = dataframe['second_reviewer_id'][0]
        else:
            if 'first_reviewer_id' in dataframe.columns:
                worker_id = dataframe['first_reviewer_id'][0]
            else:
                worker_id = 'Ready_for_ICP_review'


        if dataframe['PR'][0] >= 1:
            worker_id = 'Ready-for-physician-review'

        # Job name is the name in the Ground Truth queue, it has to be unique
        job_name = 'MRN-{mrn_id}-reviewed-{review_number}-times-{creation_time}'. \
            format(**{
                    'mrn_id': mrn_id,
                    'review_number': dataframe["PR"][0],
                    'creation_time': time.strftime('%Y-%m-%d-%H-%M',
                     time.localtime(time.time()))})
        print('Job_name', job_name)

        # Task name is the job name and description on the user UI
        task_name = 'mrn:{}-- Number of previous reviews:{}--{}'\
            .format(mrn_id, dataframe["PR"][0], worker_id)
        print('Task name:', task_name)

        # Manifest file paths
        input_manifest_uri = "s3://{}/{}".format(bucket, manifest_path)
        output_manifest_uri = 's3://{}/output/{}'.format(bucket, mrn)

        # Ground Truth job request building
        human_task_config = {
            "AnnotationConsolidationConfig": {
                "AnnotationConsolidationLambdaArn":
                os.environ['POST_LABEL_ARN'],
            },
            "PreHumanTaskLambdaArn": os.environ['PRE_LABEL_ARN'],
            "MaxConcurrentTaskCount": int(os.environ[
                'MAX_CONCURRENT_TASK_COUNT']),
            # 200 texts will be sent at a time to the workteam.
            "NumberOfHumanWorkersPerDataObject": int(os.environ[
                'NUMBER_OF_HUMAN_WORKERS_PER_DATA_OBJECT']),
            # 1 workers will be enough to label each text.
            "TaskAvailabilityLifetimeInSeconds": int(os.environ[
                'TASK_AVAILABILITY_LIFE_TIME_IN_SECONDS']),
            # Your work team has 6 hours to complete all pending tasks.
            "TaskDescription": task_name,
            "TaskTimeLimitInSeconds": int(os.environ[
                'TASK_TIME_LIMIT_IN_SECONDS']),
            # Each text must be labeled within 5 minutes.
            "TaskTitle": task_name,
            "UiConfig": {
                "UiTemplateS3Uri": complete_template_path_uri,
            },
        }

        human_task_config["WorkteamArn"] = os.environ['PRIVATE_WORK_TEAM_ARN']
        # Creating the Ground truth label job request
        ground_truth_request = {
            "InputConfig": {
                "DataSource": {
                    "S3DataSource": {
                        "ManifestS3Uri": input_manifest_uri,
                    },
                },
                "DataAttributes": {
                    "ContentClassifiers": [
                        "FreeOfPersonallyIdentifiableInformation",
                        "FreeOfAdultContent",
                    ]
                },
            },
            "OutputConfig": {
                "S3OutputPath": output_manifest_uri,
            },
            "HumanTaskConfig": human_task_config,
            "LabelingJobName": job_name,
            "RoleArn": os.environ['GROUNDTRUTH_ROLE'],
            "LabelAttributeName": "category",
        }

        # Submit ground truth job
        sagemaker_client = boto3.client('sagemaker')
        sagemaker_client.create_labeling_job(**ground_truth_request)

        return sagemaker_client.describe_labeling_job(
            LabelingJobName=job_name)['LabelingJobStatus']

    except Exception as error:
        print(error)
        raise error