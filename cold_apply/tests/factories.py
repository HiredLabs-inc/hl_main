import random
from datetime import timedelta

import factory
import faker
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from cold_apply.models import Job, Location, Participant, Skill, SkillBullet, State
from rates.models import Country
from resume.models import Bullet, Experience, Organization, Position
from userprofile.models import OnboardingStep, Profile

User = get_user_model()

fake = faker.Faker()

custom_bullet_text = [
    "Led a cross-functional team to successfully launch a new product",
    "Implemented data-driven strategies resulting in a 20% increase in user engagement",
    "Collaborated with design and development teams to improve user interface",
    "Managed client relationships and ensured customer satisfaction",
    "Created and delivered compelling presentations to stakeholders",
    "Analyzed market trends to identify opportunities for business growth",
    "Streamlined internal processes, reducing operational costs by 15%",
    "Provided mentorship and training to junior team members",
    "Designed and executed marketing campaigns that generated leads",
    "Contributed to the development of a new feature that improved user experience",
    # Add more custom bullet texts here
]

custom_job_descriptions = [
    (
        "Software Engineer\n"
        "We are seeking a skilled and experienced Software Engineer to join our team. "
        "In this role, you will be responsible for designing, developing, and maintaining "
        "high-quality software solutions. You should have a strong background in software "
        "development, a passion for coding, and the ability to work collaboratively with "
        "cross-functional teams. If you are excited about building innovative applications "
        "that solve real-world problems, then this is the perfect opportunity for you.\n"
        "Requirements:\n"
        "- Bachelor's degree in Computer Science or related field\n"
        "- Proficiency in Python, Java, or C++\n"
        "- Experience with web application development\n"
        "- Strong problem-solving skills\n"
        "- Excellent communication and teamwork abilities\n"
        "Responsibilities:\n"
        "- Collaborate with product managers and designers to define software requirements\n"
        "- Write clean, efficient, and maintainable code\n"
        "- Conduct code reviews and provide constructive feedback\n"
        "- Debug and resolve software defects\n"
        "- Participate in architectural and design discussions\n"
        "If you are passionate about software engineering and eager to contribute to "
        "cutting-edge projects, we encourage you to apply for this position. Join our "
        "dynamic team and make an impact in the world of technology!"
    ),
    (
        "Data Analyst\n"
        "As a Data Analyst at our company, you will play a crucial role in analyzing "
        "and interpreting data to provide valuable insights and recommendations. Your "
        "responsibilities will include collecting, processing, and visualizing data to "
        "help inform business decisions and strategies. You should have a strong "
        "analytical mindset, proficiency in data analysis tools, and the ability to "
        "communicate complex findings to non-technical stakeholders.\n"
        "Requirements:\n"
        "- Bachelor's degree in Statistics, Mathematics, or related field\n"
        "- Proficiency in SQL and data visualization tools\n"
        "- Strong analytical and problem-solving skills\n"
        "- Attention to detail and accuracy\n"
        "- Excellent communication skills\n"
        "Responsibilities:\n"
        "- Collect, clean, and preprocess data from various sources\n"
        "- Perform data analysis to identify trends, patterns, and insights\n"
        "- Create visualizations and reports to present findings\n"
        "- Collaborate with teams to define data requirements\n"
        "- Provide actionable recommendations based on data analysis\n"
        "If you are passionate about data-driven decision-making and enjoy working "
        "with data to uncover valuable insights, apply now and join our data analytics team!"
    ),
    (
        "Marketing Specialist\n"
        "Our company is seeking a creative and results-driven Marketing Specialist to "
        "develop and execute marketing strategies that drive growth and engagement. "
        "In this role, you will collaborate with cross-functional teams to create "
        "compelling campaigns, manage digital channels, and analyze marketing performance. "
        "You should have a strong grasp of marketing concepts, excellent communication "
        "skills, and the ability to thrive in a fast-paced environment.\n"
        "Requirements:\n"
        "- Bachelor's degree in Marketing or related field\n"
        "- Experience in digital marketing and social media management\n"
        "- Proficiency in marketing tools and analytics platforms\n"
        "- Creative thinking and problem-solving abilities\n"
        "- Strong written and verbal communication skills\n"
        "Responsibilities:\n"
        "- Develop and implement marketing strategies and campaigns\n"
        "- Create engaging content for various marketing channels\n"
        "- Monitor and analyze marketing performance metrics\n"
        "- Collaborate with design and content teams for collateral creation\n"
        "- Stay updated with industry trends and best practices\n"
        "If you are passionate about marketing and have a track record of driving "
        "successful campaigns, join our team and help us make a positive impact in the market!"
    ),
    (
        "Product Manager\n"
        "We are looking for a skilled and enthusiastic Product Manager to lead the "
        "development and strategy of our products. As a Product Manager, you will work "
        "closely with cross-functional teams to define product roadmaps, gather customer "
        "feedback, and ensure successful product launches. You should have a strong "
        "understanding of product development lifecycles, excellent communication skills, "
        "and a passion for building innovative solutions.\n"
        "Requirements:\n"
        "- Bachelor's degree in Business, Computer Science, or related field\n"
        "- Proven experience in product management\n"
        "- Strong project management skills\n"
        "- Ability to prioritize and make strategic decisions\n"
        "- Excellent communication and collaboration abilities\n"
        "Responsibilities:\n"
        "- Define and communicate product vision and roadmap\n"
        "- Gather and analyze customer feedback and market trends\n"
        "- Collaborate with engineering and design teams on product development\n"
        "- Monitor product performance and make data-driven decisions\n"
        "- Drive successful product launches and updates\n"
        "If you are a self-motivated and strategic thinker with a passion for product "
        "innovation, apply now and help us shape the future of our products!"
    ),
]


class EmailAddressFactory(DjangoModelFactory):
    class Meta:
        model = EmailAddress

    primary = True
    verified = True


class ProfileFactory(DjangoModelFactory):
    class Meta:
        model = Profile

    # Replace with the correct path to UserFactory
    nickname = factory.Faker("first_name")
    phone = factory.Faker("phone_number")
    state = factory.Faker("state_abbr")
    city = factory.Faker("city")
    zip_code = factory.Faker("postcode")
    linkedin = factory.Faker("url")
    service_package = None  # Replace with a ServicePackage instance if needed
    is_veteran = True
    veteran_verified = True
    is_onboarded = True
    resume = None  # Replace with a FileField instance if needed
    special_training = factory.Faker("paragraph")
    special_skills = factory.Faker("paragraph")
    job_links = factory.Faker("paragraph")
    work_preferences = factory.Faker("paragraph")
    onboarding_step = OnboardingStep.COMPLETE
    dnc = factory.Faker("boolean")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = get_user_model()

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    username = factory.SelfAttribute("email")
    email = factory.LazyAttribute(lambda u: f"{u.first_name}_{u.last_name}@email.com")
    password = factory.PostGenerationMethodCall("set_password", "password")
    profile = factory.RelatedFactory(ProfileFactory, "user")

    # Associate the created EmailAddress with this user
    email_address = factory.RelatedFactory(
        EmailAddressFactory, "user", email=factory.SelfAttribute("..email")
    )


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    org_type = factory.Faker("random_element", elements=["Work", "Edu", "Activity"])
    name = factory.Faker("company")
    website = factory.Faker("url")


class PositionFactory(DjangoModelFactory):
    class Meta:
        model = Position

    title = factory.Sequence(lambda n: f"{fake.job()}_{n}")


class StateFactory(DjangoModelFactory):
    class Meta:
        model = State

    name = factory.Faker("state")
    abbreviation = factory.Faker("state_abbr")


class CountryFactory(DjangoModelFactory):
    class Meta:
        model = Country

    rank = factory.Faker("random_int", min=1, max=200)
    name = factory.Faker("country")
    value = factory.Faker("pydecimal", left_digits=5, right_digits=3, positive=True)
    hdi = factory.Faker("random_element", elements=["High", "Medium", "Low"])
    zone = factory.Faker("random_element", elements=["A", "B", "C"])


class LocationFactory(DjangoModelFactory):
    class Meta:
        model = Location

    city = factory.Faker("city")
    state = factory.SubFactory(StateFactory)  # You need to define StateFactory
    country = factory.SubFactory(CountryFactory)


class JobFactory(DjangoModelFactory):
    class Meta:
        model = Job

    company = factory.SubFactory(
        OrganizationFactory
    )  # You need to define OrganizationFactory
    company_detail = factory.Faker("company")
    title = factory.SubFactory(PositionFactory)
    description = factory.LazyFunction(lambda: random.choice(custom_job_descriptions))
    status = factory.Iterator(["New", "Open", "Closed"])
    status_reason = factory.Faker(
        "random_element",
        elements=[
            "In Progress",
            "Employer Closed",
            "Admin Rejected",
            "Candidate Rejected",
            "Cycle Complete",
        ],
    )
    application_link = "http://localhost:8000"
    application_agent = factory.Faker("name")
    created_by = factory.SubFactory(UserFactory)
    updated_by = factory.SubFactory(UserFactory)
    posted_at = factory.Faker("date_time_this_year")
    salary = factory.Iterator(["20000", "30000", "40000", "50000", "60000"])
    location_detail = factory.Faker("city")
    location = factory.SubFactory(LocationFactory)
    remote = factory.Faker("sentence", nb_words=5)
    source_id = factory.Faker("uuid4")
    auto_generated = False


class SkillBulletFactory(DjangoModelFactory):
    class Meta:
        model = SkillBullet

    skill = factory.Iterator(
        Skill.objects.all()
    )  # Replace with the correct path to SkillFactory


class BulletFactory(DjangoModelFactory):
    class Meta:
        model = Bullet

    text = factory.Iterator(custom_bullet_text)
    type = factory.Faker("random_element", elements=["Work", "Summary"])
    auto_generated = factory.Faker("boolean")

    skills = factory.RelatedFactoryList(SkillBulletFactory, "bullet", size=2)


class ExperienceFactory(DjangoModelFactory):
    class Meta:
        model = Experience

    start_date = factory.Faker("date_this_decade")
    end_date = factory.LazyAttribute(lambda o: o.start_date + timedelta(days=365))
    org = factory.Iterator(
        Organization.objects.all()
    )  # Replace with the correct path to OrganizationFactory
    position = factory.Iterator(
        Position.objects.all()
    )  # Replace with the correct path to PositionFactory

    bullets = factory.RelatedFactoryList(BulletFactory, "experience", size=5)


class ParticipantFactory(DjangoModelFactory):
    class Meta:
        model = Participant

    user = factory.SubFactory(UserFactory)
    active = True
    current_step = None
    jobs = factory.RelatedFactoryList(JobFactory, "participant", size=10)
    experiences = factory.RelatedFactoryList(ExperienceFactory, "participant", size=3)


class SkillFactory(DjangoModelFactory):
    class Meta:
        model = Skill

    title = factory.Faker(
        "word"
    )  # You can adjust the data generation strategy if needed
    type = factory.Faker("random_element", elements=["Hard", "Soft"])
