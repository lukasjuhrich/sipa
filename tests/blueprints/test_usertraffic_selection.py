import pytest
from flask_login import AnonymousUserMixin

from sipa.blueprints.generic import TrafficUserSelector
from sipa.model.user import AuthenticatedUserMixin


class UnauthenticatedUser(AnonymousUserMixin):
    has_connection = False


class ConnectedUser(AuthenticatedUserMixin):
    has_connection = True


class DisconnectedUser(AuthenticatedUserMixin):
    has_connection = False


def test_both_unauthenticated():
    user = UnauthenticatedUser()
    selector = TrafficUserSelector(user, user)

    assert selector.user_selection is None
    assert not selector.prohibited_by_state
    assert not selector.different_persons_accessing


def test_both_authenticated():
    user = ConnectedUser()
    selector = TrafficUserSelector(user, user)

    assert selector.user_selection == user
    assert not selector.prohibited_by_state
    assert not selector.different_persons_accessing


def test_only_logged_in():
    current_user = ConnectedUser()
    ip_user = UnauthenticatedUser()
    selector = TrafficUserSelector(current_user, ip_user)

    assert selector.user_selection == current_user
    assert not selector.prohibited_by_state


def test_only_by_ip():
    current_user = UnauthenticatedUser()
    ip_user = ConnectedUser()
    selector = TrafficUserSelector(current_user, ip_user)

    assert selector.user_selection == ip_user
    assert not selector.prohibited_by_state


def test_two_different_authenticated():
    current_user = ConnectedUser()
    ip_user = ConnectedUser()
    selector = TrafficUserSelector(current_user, ip_user)

    assert selector.user_selection == ip_user
    assert not selector.prohibited_by_state
    assert selector.different_persons_accessing


def test_prohibition_by_state():
    current_user = DisconnectedUser()
    ip_user = UnauthenticatedUser()  # if it were authenticated, he would have access.
    selector = TrafficUserSelector(current_user, ip_user)

    # We don't care about the selection in this case, the redirection
    # has to be done manually by the frontend thing
    assert selector.user_selection is not None
    assert selector.prohibited_by_state
    assert not selector.different_persons_accessing
