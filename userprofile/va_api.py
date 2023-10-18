import requests
from django.conf import settings
from django.core.exceptions import BadRequest

# import userprofile.forms

VA_CONFIRM_ENDPOINT = (
    "https://sandbox-api.va.gov/services/veteran-confirmation/v1/status"
)


class VAApiException(Exception):
    pass


def confirm_veteran_status(user):
    response = requests.post(
        VA_CONFIRM_ENDPOINT,
        headers={"Content-Type": "application/json", "apiKey": settings.VA_API_KEY},
        json={
            "firstName": user.first_name,
            "lastName": user.last_name,
            "birthDate": str(user.profile.birthdate),
            "streetAddressLine1": user.profile.address,
            "city": user.profile.city,
            "zipCode": user.profile.zip_code,
            "state": user.profile.state,
            "country": user.profile.country,
        },
    )

    as_json = response.json()
    if response.ok:
        return as_json["veteran_status"] == "confirmed"

    if as_json.get("errors"):
        if response.status_code == 400:
            error_message = ", ".join(
                    [
                        error["detail"]
                        for error in as_json["errors"]
                        if error["status"] == "400"
                    ]
            )
            raise BadRequest(error_message)
        raise VAApiException(as_json["errors"][0]["detail"])
    else:
        raise VAApiException(as_json["message"])
