import factory
from datetime import date, timedelta
from factory import fuzzy, LazyAttribute

from cost_index.models import ApartmentRevaluation
from cost_index.utils import calculate_end_value, determine_date_index


class ApartmentRevaluationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApartmentRevaluation

    start_date = fuzzy.FuzzyDate(date(1991, 1, 1), date(2020, 9, 15))
    end_date = LazyAttribute(lambda o: o.start_date + timedelta(days=365))

    start_right_of_occupancy_payment = fuzzy.FuzzyDecimal(99.00, 9999999.99)
    start_cost_index_value = LazyAttribute(lambda o: determine_date_index(o.start_date))
    end_cost_index_value = LazyAttribute(lambda o: determine_date_index(o.end_date))
    end_right_of_occupancy_payment = LazyAttribute(
        lambda o: calculate_end_value(
            o.start_right_of_occupancy_payment, o.start_date, o.end_date
        )
    )
    alteration_work = fuzzy.FuzzyDecimal(99.00, 59999.99)
