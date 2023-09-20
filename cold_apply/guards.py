# from django.shortcuts import redirect
#
#
# def sign_up_completed(view):
#     def decorator(request, *args, **kwargs):
#         # test for sign up complete here
#         if not request.user.profile.is_onboarded:
#             # return render(request, "not_allowed.html")
#             return redirect("userprofile:sign_up")
#         return view(request, *args, **kwargs)
#
#     return decorator
