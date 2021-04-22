"""
preprocesslayer labmda function for IPAC-CLABSI
Purpose
-------
Read excell file, seperate into separate patient files, generate 7 days
 Indection Windows plots,
  total timeline plot per patient and save patient csv into s3 bucekt.
Patient files are saved as {mrn}.csv in source-csv folder, will generate
 the job-creation lambda which in terms triggers Sagemaker GroundTruth Module.

-----------------

* csv - tabular data with the patient information
"""
import os
import json
from datetime import timedelta
import datetime
import io
from io import StringIO
from matplotlib.pylab import plt
import pandas as pd
import boto3

s3_path = os.environ.get('S3_raw')
patient_processed = os.environ.get('patient_bucket')


def write_dataframe_to_csv_on_s3(dataframe, filename, bucket):
    """
    Write a dataframe to a CSV on S3
    ----------
    fieldname : dataframe
        Pandas dataframe
    fieldname: filename:
        string
    filename: bucket
        string

    """
    # Create buffer
    csv_buffer = StringIO()

    # Write dataframe to buffer
    dataframe.to_csv(csv_buffer)

    # Create S3 object
    s3_resource = boto3.resource("s3")

    # Write buffer to S3 object
    s3_resource.Object(bucket, filename).put(
        Body=csv_buffer.getvalue(),
        ServerSideEncryption="aws:kms",
    )


def relative_time_in_days(end_date, start_date):
    """
    Returns the difference between dates in day unit.
    """
    try:
        difference = (end_date - start_date).days
    except ValueError:
        difference = 0
    return difference


def plot_timeline(dataframe, patient):
    """
    Generate the timeline plot for a patient
    Columns
    =======
        ['encntr_num', 'nursing_unit_short_desc',
         'beg_effective_dt_tm','end_effective_dt_tm',
         'facility_name_src', 'collection_dt_tm',
        'mrn', 'encntr_type_desc_src_at_collection',
        'admit_dt_tm', 'clinical_event_code_desc_src',
        'collection_date_id', 'loc_room_desc_src_at_collection',
        'loc_bed_desc_src_at_collection', 'disch_dt_tm',
        'disch_disp_desc_src', 'lab_result',
        'med_service_desc_src_at_collection',
        'nursing_unit_desc_at_collection',
        'nursing_unit_short_desc_at_collection',
        'organism',
        'result_interpretation_desc_src',
        'specimen_type_desc_src', 'transfer_in_to_collect',
        'transfer_out_to_collect','ce_dynamic_label_id',
        'doc_set_name_result', 'encntr_id',
        'first_activity_start_dt_tm',
        'first_catheter_type_result',
        'first_dressing_type_result',
        'first_site_result',
        'last_activity_end_dt_tm',
        'line_tube_drain_insertion_seq',
        'line_insert_to_collection',
        'line_remove_to_collect',
        'last_temperature_result_pre_collection',
        'name_last','name_first',
        'birth_date_id','gender_desc_src','bc_phn',
        'home_addr_patient_postal_code_forward_sortation_area']

    DataTime events
    ===============
    - beg_effective_dt_tm = Nursing unit (ICU) admission date
    - end_effective_dt_tm = Nursing unit (ICU) discharge date
    - collection_dt_tm = Positive blood collection date
    - admit_dt_tm = Admission date (begin of stay)
    - disch_dt_tm = Discharge date (end of stay)
    - first_activity_start_dt_tm = Catheter insertion
    - last_activity_end_dt_tm = Catheter removal
    """
    print('Generating timeline plot for {}'.format(patient))
    # Convert all datetime values to datetime
    datetime_column_names = [
        'beg_effective_dt_tm',
        'end_effective_dt_tm',
        'collection_dt_tm',
        'admit_dt_tm',
        'disch_dt_tm',
        'first_activity_start_dt_tm',
        'last_activity_end_dt_tm',
    ]
    # Convert all date to to datetime format, the input data is mm-dd-yyyy
    for column_name in datetime_column_names:
        dataframe[column_name] = pd.to_datetime(
            dataframe[column_name], errors='coerce', format='%m/%d/%Y')
    #
    fig, axis = plt.subplots(figsize=(
        12, 3 + len(dataframe['collection_dt_tm'].unique()) / 4), dpi=300)
    collection_times = []
    plotted_organisms = []
    x_scale_label = {}
    y_scale_label = []
    dates = {}
    # Generate a list of organisms,
    # thus same organism found can be shown as the same color
    unique_organisms = []
    for index in dataframe.index:
        organism = dataframe.loc[index, 'organism']
        unique_organisms.append(organism)
    # Iterate through all records and add them to the plot
    for index in dataframe.index:
        # Organism found for this record
        organism = dataframe.loc[index, 'organism']

        # Calcululate the relative date from admission
        day = {
            key: relative_time_in_days(
                dataframe.loc[index, key], sorted(dataframe['admit_dt_tm'])[0])
            for key in datetime_column_names
        }
        # 3 bar graph plots: patient visit, nuring unit, central line
        bar_graphs = {
            'Patient visit': {
                'start': 'admit_dt_tm',
                'stop': 'disch_dt_tm',
                'y': 0,
                'color': [0.8, 0.8, 0.8],
            },
            dataframe.loc[index, 'nursing_unit_short_desc']: {
                'start': 'beg_effective_dt_tm',
                'stop': 'end_effective_dt_tm',
                'y': 1,
                'color': [0.6, 0.6, 0.6],
            },
            'Central line': {
                'start': 'first_activity_start_dt_tm',
                'stop': 'last_activity_end_dt_tm',
                'y': 2,
                'color': [0.4, 0.4, 0.4],
            },
        }
        # One type of markers for the positive blood collection dates
        marker_graphs = {
            'Blood collection': {
                'start': 'collection_dt_tm',
                'y': 0,
                'color': [0.8, 0.2, 0.2],
            },
        }
        # bar graphs: patient visit, nuring unit, central line
        for label in bar_graphs:
            period = (
                dataframe.loc[index, bar_graphs[label]['start']],
                dataframe.loc[index, bar_graphs[label]['stop']]
            )
            # Do not plot the same period twice
            if label not in dates:
                dates[label] = []
            if period not in dates[label]:
                # Bar plot for the period
                axis.bar(
                    [day[bar_graphs[label]['start']]],
                    [0.8],
                    width=day[bar_graphs[label]['stop']] -
                    day[bar_graphs[label]['start']],
                    bottom=bar_graphs[label]['y'] + 0.1,
                    color=bar_graphs[label]['color'],
                    # edgecolor='w',
                    # linewidth=4,
                    align='edge',
                )
                # Put marker to the start and stop date, thus if there is
                # a missing date it can still be seen.
                axis.plot(
                    [day[bar_graphs[label]['start']]],
                    [bar_graphs[label]['y'] + 0.5],
                    'k>',
                )
                axis.plot(
                    [day[bar_graphs[label]['stop']]],
                    [bar_graphs[label]['y'] + 0.5],
                    'k<',
                )
                dates[label].append(period)
                x_scale_label[day[bar_graphs[label]['start']]] = dataframe.loc[
                    index, bar_graphs[label]['start']]
                x_scale_label[day[bar_graphs[label]['stop']]] = dataframe.loc[
                    index, bar_graphs[label]['stop']]
            if label not in y_scale_label:
                y_scale_label.append(label)
        for label in marker_graphs:
            # Blood collection
            if float(
                    day[marker_graphs[
                        label]['start']]) not in collection_times:
                if organism not in plotted_organisms:
                    axis.plot(
                        [day[marker_graphs[label]['start']]],
                        [marker_graphs[label]['y'] + 0.5],
                        marker='o',
                        markersize=14,
                        linestyle='',
                        color=plt.cm.tab10(unique_organisms.index(organism)),
                        label=organism.replace(', ', "\n"),
                    )
                    plotted_organisms.append(organism)
                else:
                    axis.plot(
                        [day[marker_graphs[label]['start']]],
                        [marker_graphs[label]['y'] + 0.5],
                        marker='o',
                        markersize=14,
                        linestyle='',
                        color=plt.cm.tab10(unique_organisms.index(organism)),
                    )
                axis.plot(
                    [day[marker_graphs[label]['start']]],
                    [marker_graphs[label]['y'] + 0.5],
                    'wo',
                    markersize=5,
                    color='0.8'
                )
                collection_times.append(
                    float(day[marker_graphs[label]['start']]))
                x_scale_label[day[
                    marker_graphs[label]['start']]] = dataframe.loc[
                    index, marker_graphs[label]['start']]
            if label not in dates:
                dates[label] = []
            dates[label].append(day[marker_graphs[label]['start']])
    axis.set_yticks([value + 0.5 for value in range(len(y_scale_label))])
    axis.set_yticklabels(y_scale_label)
    axis.set_ylim(0, len(y_scale_label))
    axis.set_xticks(list(x_scale_label.keys()))
    axis.set_xticklabels([
        str(value)[:10] for value in x_scale_label.values()], rotation=90)
    axis.set_xlabel('Date')
    axis.set_axisbelow(True)
    plt.legend(
        bbox_to_anchor=(1.04, 1), loc='upper left',
        ncol=1, title='Positive blood sample')
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    image = buf.read()
    s3_resource = boto3.resource("s3")
    # saving the patient total timeline
    # plots to processed/images/patient/timeline.png
    filename = f'images/{patient}/timeline.png'
    bucket = os.environ['patient_bucket']
    print('Timeline plot path for patient {}: {}'.format(patient, filename))
    s3_resource.Object(bucket, filename).put(
        Body=image, ServerSideEncryption="aws:kms")


def get_start_end_time(dataframe):
    """
    Creating middle_time, start_time, end_time columns for creation
    of Infection Time Window plots, for each collection date.
    ----------
    fieldname : dataframe
        Pandas dataframe
    Returns
    --------
    dataframe_

        temp dataframe for ploting total timelines

    """

    for i in dataframe.index:

        dataframe.loc[i, 'middle_time'] = dataframe.loc[
            i, 'collection_dt_tm']

        dataframe.loc[i, 'start_time'] = dataframe.loc[
            i, 'collection_dt_tm'] - timedelta(days=3)

        dataframe.loc[i, 'end_time'] = dataframe.loc[
            i, 'collection_dt_tm'] + timedelta(days=3)
    return dataframe


def estimate_text_size(text):
    """
    Provide a text size estimate based on the length of the text
    Parameters
    ----------
    text: string
        Text meant to print on the IWP plot
    Returns
    -------
    fontsize: float
        Estimated best fontsize
    """
    fontsize = 12
    if len(text) > 50:
        fontsize -= (len(text) - 50) / 5
    if fontsize < 5:
        fontsize = 5
    return fontsize


def generate_iwp_plot(dataframe, temperature, plot_index, patient):
    """
    Generate individual IWP plot for each positive blood collection.
    """
    dataframe = dataframe.copy()
    # Convert all datetime values to datetime
    datetime_column_names = [
        'beg_effective_dt_tm',
        'end_effective_dt_tm',
        'collection_dt_tm',
        'admit_dt_tm',
        'disch_dt_tm',
        'first_activity_start_dt_tm',
        'last_activity_end_dt_tm',
    ]
    # Convert all date to to datetime format, the input data is mm-dd-yyyy
    for column_name in datetime_column_names:
        dataframe[column_name] = pd.to_datetime(
            dataframe[column_name], errors='coerce',
            # format='%m/%d/%Y',
        )
    collection_date = dataframe.loc[plot_index, 'collection_dt_tm']
    day3 = pd.Timedelta(days=3)
    fig, axis = plt.subplots(
        2, 1, True, False,
        figsize=(7, 7), dpi=150,
        gridspec_kw={'height_ratios': [1, 2.5]},
    )
    # Generate the temperature plot - top portion
    # Fever limit, above limit the
    temperature_limit = 38.0
    # Mark the temperature limit (38 C) with a solid line
    axis[0].plot_date(
        [collection_date - day3, collection_date + day3],
        [temperature_limit, temperature_limit],
        'k-',
        color='0.4',
    )

    # Plot all temperature information

    for temperature_index in temperature.index:
        temp_date = temperature.loc[temperature_index, 'event_end_dt_tm']
        value = temperature.loc[temperature_index, 'result_val']
        try:
            # Above limit the marker is red
            if value < temperature_limit:
                markercolor = '0.4'
            else:
                markercolor = [0.8, 0.2, 0.2]
            # Plot the dates - temperature information
            axis[0].plot_date(
                temp_date, value, 'wo',
                markeredgecolor=markercolor,
                markersize=6,
                markeredgewidth=4,
            )
        except ValueError:
            print('failure in plotting temperature')

    # Plot catheter start and end
    if not (pd.isnull(dataframe.loc[plot_index, 'first_activity_start_dt_tm'])
            or pd.isnull(dataframe.loc[
                plot_index, 'last_activity_end_dt_tm'])):
        axis[1].plot_date(
            [dataframe.loc[plot_index, 'first_activity_start_dt_tm'],
                dataframe.loc[plot_index, 'last_activity_end_dt_tm']],
            [0.1, 0.1],
            'k-',
            color='0.8',
            linewidth=60,
        )
    catheter_information = ' - '.join((
        str(dataframe.loc[plot_index, 'first_site_result']),
        str(dataframe.loc[plot_index, 'first_catheter_type_result']),
    ))
    axis[1].text(
        collection_date - pd.Timedelta(days=2),
        0.09,
        catheter_information,
        size=estimate_text_size(catheter_information),
    )
    # Plot nursing unit start and end
    if not (pd.isnull(dataframe.loc[plot_index, 'beg_effective_dt_tm'])
            or pd.isnull(dataframe.loc[plot_index, 'end_effective_dt_tm'])):
        axis[1].plot_date(
            [dataframe.loc[plot_index, 'beg_effective_dt_tm'],
                dataframe.loc[plot_index, 'end_effective_dt_tm']],
            [0.3, 0.3],
            'k-',
            color='0.8',
            linewidth=60,
        )
    nursing_inforamtion = ' - '.join((
        str(dataframe.loc[plot_index,
            'nursing_unit_short_desc_at_collection']),
        str(dataframe.loc[plot_index,
            'med_service_desc_src_at_collection']),
    ))
    axis[1].text(
        collection_date - pd.Timedelta(days=2),
        0.29,
        nursing_inforamtion,
        size=estimate_text_size(nursing_inforamtion),
    )
    # Helper line for organism and collection dates
    axis[1].plot_date(
        [dataframe.loc[plot_index, 'collection_dt_tm'] for _ in range(2)],
        [0.5, 0.63],
        'k-',
        color='0.8',
    )
    # Plot all collection dates
    for index in dataframe.index:
        axis[1].plot_date(
            [dataframe.loc[index, 'collection_dt_tm']],
            [0.5],
            'ko',
            color='0.4',
            markersize=16
        )
    # Corresponding organism
    organism_information = dataframe.loc[plot_index, 'organism']

    axis[1].text(
        collection_date - datetime.timedelta(days=1.2),
        0.65,
        organism_information,
        size=12,
    )
    # Axis settings
    axis[0].set_ylabel('Temperature /C')
    axis[0].set_ylim(35, 41)
    axis[0].set_yticks(range(35, 42))
    axis[0].set_yticklabels(['{}.0'.format(value) for value in range(35, 42)])
    axis[0].grid(axis='y', linestyle='-')
    collection_date = pd.to_datetime(collection_date)
    # print((collection_date - day3).date(),(collection_date + day3).date())
    axis[0].set_xlim(
        pd.to_datetime(collection_date - day3).date(),
        pd.to_datetime(collection_date + day3).date())
    axis[1].set_ylim(0, 0.8)
    axis[1].set_yticks([0.1, 0.3, 0.5, 0.7])
    axis[1].set_yticklabels([
        'Central line',
        'Nursing unit',
        'Blood sample',
        'Organism',
    ])
    for label in axis[1].get_xticklabels():
        label.set_ha('center')
        label.set_rotation(90)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    image = buf.read()
    s3_resource = boto3.resource("s3")
    # saving the infection window time plots
    #  to processed/images/patient/IWP/plots_{plot-number}.png
    # filename = f'images/{patient}/IWP/plots_{plot_index}.png'
    # Modify filename because ordering plot_index results:
    #        1, 10, 11, 12, 2, 3 instead of 1, 2, 3, 10, 11, 12
    filename = 'images/{patient}/IWP/plots_{index}.png'.format(**{
        'patient': patient,
        'index': str(plot_index).rjust(2, '0'),
    })

    bucket = os.environ['patient_bucket']
    s3_resource.Object(bucket, filename).put(
        Body=image, ServerSideEncryption="aws:kms")

    return True

def preprocess(obj):

    '''
    Recieves s3 object from boto3, converts to excell sheet,
    and then converts to 3 dataframes.
    changes the dataframes column names to lower case,
    and joins organism dataframe with patient dataframe.
    ----------
    fieldname : obj
    fieldname: s3 object
    Returns
    -------
    dataframe for patients, dataframe for temperature
    '''

    data = obj['Body'].read()
    xls = pd.ExcelFile(data)
    dataframe_patients = pd.read_excel(xls, 'Sheet1')
    dataframe_temperature = pd.read_excel(xls, 'Sheet2')
    dataframe_organism = pd.read_excel(xls, 'Sheet3')
    dataframe_patients.rename(str.lower, axis='columns',inplace=True)
    dataframe_temperature.rename(str.lower, axis='columns',inplace=True)
    dataframe_organism.rename(str.lower, axis='columns', inplace=True)

    if 'Unnamed: 0' in dataframe_patients.columns:
        dataframe_patients.drop(columns='Unnamed: 0', inplace=True)
    if 'Unnamed: 0' in dataframe_temperature.columns:
        dataframe_temperature.drop(columns='Unnamed: 0', inplace=True)
    if 'Unnamed: 0' in dataframe_organism.columns:
        dataframe_organism.drop(columns='Unnamed: 0', inplace=True)

    dataframe_organism.set_index(['mrn', 'encntr_num'], inplace=True)
    for i in dataframe_patients.index:
        mrn = dataframe_patients.loc[i,'mrn']
        enct_num = dataframe_patients.loc[i, 'encntr_num']
        dataframe_patients.loc[i, 'organism'] = " , ".join(dataframe_organism.loc[(mrn,enct_num),'organism_desc_src'].unique())

    return dataframe_patients, dataframe_temperature

def lambda_handler(event, context):
    '''
    Recieves event, by getting triggered with
    the upload of the excell file from storage gateway
    sends individual patient file and
    uploads to source-csv and patient plots to the clabsi bucket .

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
    '''
    print(context)
    s3_client = boto3.client('s3')
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    dataframe_patients, dataframe_temperature = preprocess(obj)

    try:
        for patient in dataframe_patients['mrn'].unique():

            data = dataframe_patients[dataframe_patients['mrn']
                                      == patient].copy()
            data.sort_values(
                ['collection_dt_tm'], inplace=True, ascending=True)
            data.reset_index(inplace=True)
            data.drop('index', axis=1, inplace=True)

            temperature = dataframe_temperature[
                dataframe_temperature['mrn'] == patient].copy()
            temperature.sort_values(
                ['collection_dt_tm'], inplace=True, ascending=True)
            temperature.reset_index(inplace=True)
            temperature.drop('index', axis=1, inplace=True)
            # Generate timeline plot
            plot_timeline(data, patient)
            # Generate IWP plots, one per each collection date
            for plot_index in data.index:
                generate_iwp_plot(data, temperature, plot_index, patient)
            # Generate the CSV file to trigger job creation
            write_dataframe_to_csv_on_s3(
                data,
                f'{os.environ["patient_folder"]}/{patient}.csv',
                patient_processed)
    except Exception as error:
        print(error)
        raise error
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')}
