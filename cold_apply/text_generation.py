from typing import List

import vertexai
from django.conf import settings
from vertexai.language_models import TextGenerationModel

from cold_apply.models import Job, Participant, Skill
from resume.models import Bullet, Experience, Position

# def generate_overview(participant: Participant):


def get_keywords(job: Job):
    """Returns a list of keywords for a job description."""
    keywords = job.keywordanalysis_set.values_list("unigram", "bigram", "trigram")
    unigrams = [unigram for unigram, _, _ in keywords]
    bigrams = [bigram for _, bigram, _ in keywords]
    trigrams = [trigram for _, _, trigram in keywords]

    return unigrams, bigrams, trigrams


def rewrite_bullet_for_job(bullet, job):
    unigrams, bigrams, trigrams = get_keywords(job)

    unigrams_list = "\n".join(unigrams)
    bigrams_list = "\n".join(bigrams)
    trigrams_list = "\n".join(trigrams)

    prompt = (
        f"Rewrite the following bullet point into a single bullet point only: '{bullet.text}' "
        f"to focus on these keywords: {unigrams_list}"
    )

    return generate_text(prompt)


def generate_overview(position: Position, job: Job = None):
    prompt = (
        ""
        "Write an overview section for a CV. The overview needs to be a minimum of 150 word and maximum 200 words with no personal pronouns and no text decoration."
        "The overview should be tailored to this job title: "
        f"{position.title}."
    )
    if job:
        unigrams, bigrams, trigrams = get_keywords(job)

        unigrams_list = "\n".join(unigrams)
        bigrams_list = "\n".join(bigrams)
        trigrams_list = "\n".join(trigrams)

        prompt += f"\n\nThe overview should focus on these keywords: {unigrams_list}"

    return generate_text(prompt)


def generate_bullets(experience: Experience, skills: List[Skill] = None, quantity=1):
    prompt = f"Write {quantity} bullet points, using 25-40 words per bullet point, with no text decoration, seperated by a | character, for a CV under this heading: '{experience.position.title}'."
    if skills:
        skills_list = "\n".join([skill.title for skill in skills])
        prompt += f"\n\nThe bullet point should focus on these skills:\n{skills_list}"

    if experience.bullet_set.count():
        existing_bullets = "\n".join(
            [bullet.text for bullet in experience.bullet_set.all()]
        )
        prompt += (
            f"\n\nHere are the bullet points you have already "
            f"written, try not to repeat them:\n{existing_bullets}"
        )

    response = generate_text(prompt)
    return [t.strip() for t in response.split("|") if t]


def generate_bullet(
    experience: Experience, skills: List[Skill] = None, job: Job = None
):
    """Generate a bullet point for a job description."""
    prompt = (
        f"Using between 25 and 40 words, no personal pronouns, and no text decoration."
        " Write five bullet points for a CV under this "
        f"work experience heading:\n{experience.position.title}."
    )

    # tailored for this job description: {job_description}}"
    if skills:
        skills_list = "\n".join([skill.title for skill in skills])
        prompt += f"\n\nThe bullet point should focus on these skills:\n{skills_list}"

    if job:
        # this seems to cause the response to be empty, need a way to summarise the job description
        # before sending it
        pass
        # prompt += f"\n\nThe bullet point should be tailored to this job description: \n{job.description[:1000]}"

    if experience.bullet_set.count():
        existing_bullets = "\n".join(
            [bullet.text for bullet in experience.bullet_set.all()]
        )
        prompt += (
            f"\n\nHere are the bullet points you have already "
            f"written, try not to repeat them:\n{existing_bullets}"
        )

    # bullet_text =

    # bullet = experience.bullet_set.create(text=bullet_text, type="Work")
    # if skills:
    #     bullet.skills.set(skills)

    return generate_text(prompt)


def generate_text(prompt: str, language_model="text-bison@001"):
    """Calls vertexai.language_models.TextGenerationModel to generate text."""
    vertexai.init(
        project=settings.GCP_PROJECT_ID,
    )
    parameters = {
        "temperature": 0.5,  # Temperature controls the degree of randomness in token selection.
        "max_output_tokens": 256,  # Token limit determines the maximum amount of text output.
        "top_p": 0.8,  # Tokens are selected from most probable to least until the sum of their probabilities equals the top_p value.
        "top_k": 40,  # A top_k of 1 means the selected token is the most probable among all tokens.
    }
    model = TextGenerationModel.from_pretrained(language_model)
    print(f"Prompt: {prompt}")
    response = model.predict(
        prompt,
        **parameters,
    )
    print("----------------------")
    print("Response:", response.text)

    return response.text
