import json
def hello(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Success! The CI/CD pipeline is working."})
    }