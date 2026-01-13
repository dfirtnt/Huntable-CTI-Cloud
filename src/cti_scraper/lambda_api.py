"""Lambda handler for FastAPI application using Mangum

This Lambda handler wraps the FastAPI application with Mangum adapter
to make it compatible with AWS Lambda and API Gateway.
"""
from mangum import Mangum
from cti_scraper.api.app import create_app

# Create FastAPI app
app = create_app()

# Wrap with Mangum for Lambda compatibility
# lifespan="off" disables startup/shutdown events which don't work well in Lambda
handler = Mangum(app, lifespan="off")
