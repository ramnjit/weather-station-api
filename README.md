# Weather API - CI/CD Demo

This repository demonstrates a complete, working CI/CD pipeline for a serverless Python application using GitHub Actions and AWS SAM.

## Synopsis

The `main` branch of this repository contains a simplified "smoke test" function that is automatically built and deployed to AWS Lambda on every push.

This project was initially a full-featured Python/Flask application with a PostgreSQL database connection. However, during development, an unresolvable tooling bug was discovered in the AWS SAM build process within the CI/CD environment, which prevented Python dependencies from being packaged correctly.

As a pragmatic engineering decision to meet a deadline, the deployed version was simplified to prove that the **end-to-end CI/CD pipeline, Infrastructure as Code, and API Gateway routing all work perfectly.**

The complete, full-featured code for the original application can be found on the **`full-backend`** branch.

---

## Live Demo

The CI/CD pipeline is active. The live "smoke test" endpoint can be accessed here:

**https://51qs8v7kni.execute-api.us-east-1.amazonaws.com/Prod/hello**

---

## CI/CD Pipeline

The workflow is defined in `.github/workflows/deploy.yml`. On every push to `main`, it automatically:
1.  Checks out the code.
2.  Sets up a Python environment.
3.  Authenticates with AWS using a secure OIDC role.
4.  Builds the application using `sam build`.
5.  Deploys the application using `sam deploy`.
