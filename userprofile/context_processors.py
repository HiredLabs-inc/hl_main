"""Values the shared public-site chrome (nav and footer) needs on every page."""

# Hired Labs-branded donation form. It is hosted by Stiles Hall, our fiscal
# agent, so the form names Stiles Hall; the donate section explains this.
DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=FSCDFRT2GALF4"


def public_site(request):
    return {"DONATE_URL": DONATE_URL}
