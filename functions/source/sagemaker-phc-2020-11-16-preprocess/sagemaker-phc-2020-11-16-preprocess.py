import json

def lambda_handler(event, context):
    return {
        "taskInput": event['dataObject']
    }