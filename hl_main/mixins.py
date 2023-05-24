from django.forms import BaseModelForm
from django.http import HttpResponse


class HtmxViewMixin:
    htmx_template = None

    def get_template_names(self):
        if self.request.headers.get("Hx-Request"):
            return [self.htmx_template]
        return [self.template_name]

    def form_valid(self, form: BaseModelForm):
        response = super().form_valid(form)

        if self.request.headers.get("Hx-Request"):
            response = HttpResponse(status=203)

        return response
