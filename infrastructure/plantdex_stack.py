from pathlib import Path

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_lambda as lambda_,
)
from aws_cdk.aws_apigatewayv2 import (
    HttpApi,
    HttpMethod,
    CorsPreflightOptions,
    CorsHttpMethod,
)
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct


class PlantDexStack(Stack):
    """
    AWS CDK stack for deploying the PlantDex backend API.

    This stack creates:
    - A Python AWS Lambda function for handling similar-plant requests.
    - An HTTP API Gateway endpoint.
    - A GET `/similar` route connected to the Lambda function.
    - A CloudFormation output containing the deployed API URL.

    The Lambda source code is loaded from the project's `src/` directory.
    The Trefle API token is passed through CDK context as an environment
    variable for the Lambda function.

    Example:
        Deploy with a Trefle token using CDK context:

        ```bash
        cdk deploy -c trefle_token=YOUR_TREFLE_TOKEN
        ```

        After deployment, CDK will output something like:

        ```text
        PlantDexApiUrl = https://abc123.execute-api.us-west-2.amazonaws.com
        ```

        You can then call the API:

        ```bash
        curl "https://abc123.execute-api.us-west-2.amazonaws.com/similar?plant=blueberry&basis=genus"
        ```
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        """
        Initialize the PlantDex CDK stack.

        Args:
            scope:
                Parent CDK construct, usually the CDK app.
            construct_id:
                Unique identifier for this stack.
            **kwargs:
                Additional stack configuration such as environment, tags,
                or synthesizer settings.

        Example:
            In your CDK app entrypoint, usually `app.py`:

            ```python
            import aws_cdk as cdk
            from infra.plantdex_stack import PlantDexStack

            app = cdk.App()

            PlantDexStack(
                app,
                "PlantDexStack",
                env=cdk.Environment(
                    account="123456789012",
                    region="us-west-2",
                ),
            )

            app.synth()
            ```
        """
        super().__init__(scope, construct_id, **kwargs)

        # Resolve project paths relative to this stack file.
        # Expected structure:
        #
        # project_root/
        #   infra/
        #     plantdex_stack.py
        #   src/
        #     lambda_handlers/
        #       similar_plants_handler.py
        project_root = Path(__file__).resolve().parents[1]
        src_path = project_root / "src"

        # Lambda function that powers the `/similar` API route.
        #
        # The handler path assumes:
        # src/lambda_handlers/similar_plants_handler.py
        #
        # with a function named:
        # lambda_handler(event, context)
        similar_plants_fn = lambda_.Function(
            self,
            "SimilarPlantsFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambda_handlers.similar_plants_handler.lambda_handler",
            code=lambda_.Code.from_asset(str(src_path)),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                # Temporary MVP approach.
                # Better later: store this in AWS Secrets Manager or SSM Parameter Store.
                #
                # Example deploy command:
                # cdk deploy -c trefle_token=YOUR_TREFLE_TOKEN
                "TREFLE_TOKEN": self.node.try_get_context("trefle_token") or "",
            },
        )

        # Public HTTP API for the PlantDex backend.
        #
        # CORS is currently open for MVP/frontend development.
        # For production, replace `allow_origins=["*"]` with your frontend domain.
        api = HttpApi(
            self,
            "PlantDexHttpApi",
            cors_preflight=CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[CorsHttpMethod.GET, CorsHttpMethod.OPTIONS],
                allow_headers=["Content-Type"],
            ),
        )

        # Connect API Gateway to the Lambda function.
        integration = HttpLambdaIntegration(
            "SimilarPlantsIntegration",
            similar_plants_fn,
        )

        # GET /similar
        #
        # Example request:
        # /similar?plant=blueberry&basis=family&max_results=10&image_only=true
        api.add_routes(
            path="/similar",
            methods=[HttpMethod.GET],
            integration=integration,
        )

        # Output the API base URL after deployment.
        #
        # Example output:
        # https://abc123.execute-api.us-west-2.amazonaws.com
        CfnOutput(
            self,
            "PlantDexApiUrl",
            value=api.api_endpoint,
        )