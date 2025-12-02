from typing import Callable
import pytest
from sentry_sdk.scrubber import EventScrubber, DEFAULT_DENYLIST
from unittest.mock import MagicMock
import sentry_sdk
from application_form.tests.conftest import mock_sentry
""" 
Simple tests to validate Sentry SDK scrubs sensitive info such as ssn suffixes
"""

fake_ssn_suffix = "-9101"
fake_user_name = "matti"

def sentry_test_func():
    ssn_suffix = fake_ssn_suffix  # This should be scrubbed
    user_name = fake_user_name        # This should remain
    raise ValueError("Testing Sentry Scrubbing")

def create_sentry_test_event(function: Callable) -> dict:
    """Executes the given callable inside a wrapper that captures it in a 
    Sentry exception message. Used for unit tests.

    Args:
        function (Callable): any Python callable

    Returns:
        dict: a Sentry error frame as a Python dict
    """    
    sentry_client = sentry_sdk.Hub.current.client
    sentry_client.transport = MagicMock()

    # call the given callable wrapped into sentry_sdk exception handling
    try:
        function()
    except ValueError:
        sentry_sdk.capture_exception()

    # Get the event passed to the mock transport
    # call_args[0][0] gets the first positional argument of the first call
    event = sentry_client.transport.capture_event.call_args[0][0]
    return event

def test_sentry_ssn_suffix_scrubbed_from_local_variables(mock_sentry):
    """
    Verifies that a local variable named 'ssn_suffix' is replaced 
    with [FILTERED_NATIONAL_IDENTIFICATION_NUMBER] in the stack trace.
    """

    event = create_sentry_test_event(sentry_test_func)
    frames = event['exception']['values'][0]['stacktrace']['frames']
    
    # Find the frame where our test function ran (usually the last one)
    target_frame = frames[-1]
    
    # Verify the sensitive variable is scrubbed
    assert 'ssn_suffix' in target_frame['vars']
    assert fake_ssn_suffix not in target_frame['vars']['ssn_suffix'] # noqa: E501
    
    # Verify non-sensitive variables remain untouched
    # use "in" because tests might sometimes wrap the message in '' which messes up
    # the == comparison
    assert fake_user_name in target_frame['vars']['user_name']

def test_sentry_ssn_suffix_scrubbed_from_extra_context(mock_sentry):
    """
    Verifies that 'ssn_suffix' is scrubbed if it appears in 
    dictionaries/context data (simulating request.data).
    """
    sentry_client = sentry_sdk.Hub.current.client
    sentry_client.transport = MagicMock()

    # Set context explicitly (similar to how Django sets request data)
    sentry_sdk.set_context("my_data", {
        "username": "matti",
        "ssn_suffix": fake_ssn_suffix
    })
    
    sentry_sdk.capture_message("User login event")
    
    # Get the event
    event = sentry_client.transport.capture_event.call_args[0][0]
    
    # Check the contexts section
    user_data = event['contexts']['my_data']
    
    assert fake_user_name in user_data['username']
    assert fake_ssn_suffix not in user_data['ssn_suffix']