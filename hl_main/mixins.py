from django.forms import BaseModelForm
from django.http import HttpResponse


class HtmxViewMixin:
    htmx_template = None
    refresh_on_save = False
    # used to trigger modal close
    empty_response_on_save = False

    def get_template_names(self):
        if self.request.headers.get("Hx-Request"):
            return [self.htmx_template or self.template_name]
        return [self.template_name]

    def form_valid(self, form):
        response = super().form_valid(form)
        if "Hx-Request" in self.request.headers:
            # Could use HX-Redirect as it does the same but it causes a scroll to top
            # so HX-Refresh looks better, use HX-Redirect if
            # you need full page reload navigation to somewhere else e.g:
            # "HX-Redirect": reverse(
            #     "cold_apply:participant_experience_list",
            #     kwargs={"pk": self.object.experience.participant_id},
            # )
            headers = {"Hx-Refresh": "true"} if self.refresh_on_save else {}

            return HttpResponse(
                headers=headers, status=204 if self.empty_response_on_save else 200
            )

        return response
