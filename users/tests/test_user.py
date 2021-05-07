import pytest
from django.contrib.auth import get_user_model


class TestUsersManagers:
    @pytest.mark.django_db
    def test_create_user(self):
        User = get_user_model()
        user = User.objects.create_user(email="normal@user.com")
        assert user.email == "normal@user.com"
        assert user.is_active
        assert not user.is_superuser
        assert not user.is_staff
        with pytest.raises(AttributeError):
            getattr(user, "username")
        with pytest.raises(TypeError):
            assert User.objects.create_user()
        with pytest.raises(ValueError):
            assert User.objects.create_user(email="")
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="foo")

    @pytest.mark.django_db
    def test_create_superuser(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser("super@user.com", "foo")
        assert admin_user.email == "super@user.com"
        assert admin_user.is_active
        assert admin_user.is_staff
        assert admin_user.is_superuser
        with pytest.raises(AttributeError):
            getattr(admin_user, "username")
        with pytest.raises(ValueError):
            User.objects.create_superuser(
                email="super@user.com", password="foo", is_superuser=False
            )
