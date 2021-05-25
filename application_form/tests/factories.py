import factory
import uuid
from factory import fuzzy
from faker import Faker

from application_form.enums import AttachmentType, FileFormat
from application_form.models import Applicant, Application, File
from users.models import Profile

fake = Faker("fi_FI")


def sequence(number):
    """
    :param number:
    :return: a dict that contains random data
    """
    return {
        "data1": f"text{number}",
        "data2": f"text{number}",
    }


class ProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Profile


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application


class ApplicantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Applicant


class FileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = File

    id = uuid.uuid4()
    application = factory.SubFactory(ApplicationFactory)
    profile = factory.SubFactory(ProfileFactory)
    attachment_name = fuzzy.FuzzyChoice(list(AttachmentType))
    file_name = fuzzy.FuzzyText(length=20)
    location_id = fuzzy.FuzzyText(length=20)
    file_format = fuzzy.FuzzyChoice(list(FileFormat))
    metadata = factory.Sequence(sequence)
