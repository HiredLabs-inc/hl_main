from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        super().populate_username(request, user)
        user.username = user.email

    def is_open_for_signup(self, request):
        # Signup goes through userprofile.signup (email link first, then password).
        return False

    def get_client_ip(self, request):
        # Clients can send their own X-Forwarded-For; Cloud Run appends the real
        # client address, so trust only the last entry (allauth uses the first).
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[-1].strip()
        return request.META.get("REMOTE_ADDR")


def user_display_email(user):
    return user.email
