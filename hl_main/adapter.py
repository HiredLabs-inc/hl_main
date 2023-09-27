from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        super().populate_username(request, user)
        user.username = user.email


def user_display_email(user):
    return user.email
