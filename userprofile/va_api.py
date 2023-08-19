import requests
from django.conf import settings
from django.core.exceptions import BadRequest

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
            "firstName": "Alfredo",
            "lastName": "Armstrong",
            "birthDate": "1993-06-08",
            # "middleName": "M",
            # "gender": "M",
            "streetAddressLine1": "17020 Tortoise St",
            "city": "Round Rock",
            "zipCode": "78664",
            "state": "TX",
            "country": "USA",
            # "homePhoneNumber": "555-555-5555",
            # "mothersMaidenName": "Smith",
            # "birthPlaceCity": "Johnson City",
            # "birthPlaceState": "MA",
            # "birthPlaceCountry": "USA",
        },
    )
    # raise BadRequest("Invalid Address")
    as_json = response.json()
    if response.ok:
        return as_json["veteran_status"] == "confirmed"

    if as_json.get("errors"):
        if response.status_code == 400:
            raise BadRequest(
                ", ".join(
                    [
                        error["detail"]
                        for error in as_json["errors"]
                        if error["status"] == "400"
                    ]
                )
            )
        raise VAApiException(as_json["errors"][0]["detail"])
    else:
        raise VAApiException(as_json["message"])
