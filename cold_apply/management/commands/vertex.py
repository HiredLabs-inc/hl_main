import vertexai
from django.core.management import BaseCommand
from google.cloud import aiplatform, secretmanager
from vertexai.language_models import TextGenerationModel


class Command(BaseCommand):
    def handle(self, *args, **options):
        vertexai.init(
            project="redmond-test-project",
        )
        parameters = {
            "temperature": 0,  # Temperature controls the degree of randomness in token selection.
            "max_output_tokens": 256,  # Token limit determines the maximum amount of text output.
            "top_p": 0.8,  # Tokens are selected from most probable to least until the sum of their probabilities equals the top_p value.
            "top_k": 40,  # A top_k of 1 means the selected token is the most probable among all tokens.
        }
        model = TextGenerationModel.from_pretrained("text-bison@001")
        response = model.predict(
            "Write a bullet point for a CV tailored for this job description: Looking for a software engineer with 5+ years of experience in Python, Java, and C++.",
            **parameters,
        )

        print(f"Response from Model: {response.text}")
