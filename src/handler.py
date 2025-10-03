import json

# simple lambda function that returns successful JSON response.
# used to showcase CI/CD pipeline and that the API Gateway works
def hello(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Success! The CI/CD pipeline is working."})
    }