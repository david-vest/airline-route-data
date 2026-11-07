#!/usr/bin/python
from collections import defaultdict
import json
import os
import re
import sys
import time

from curl_cffi import requests
from geopy.distance import geodesic



def clean_coord_str(val):
    if not val:
        return "0.0"
    s = str(val).strip().lower()
    negate = "s" in s or "w" in s
    s = s.replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if match:
        num = match.group(0)
        val_abs = num[1:] if num.startswith(("+", "-")) else num
        return f"-{val_abs}" if (negate or num.startswith("-")) else val_abs
    return "0.0"


def fetch(session, url, parse, allow_not_found=False):
    for attempt in range(1, 4):
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 404 and allow_not_found:
                return None
            if (response.headers.get("cf-mitigated") == "challenge"
                    or "window._cf_chl_opt" in response.text):
                raise ValueError(
                    "Cloudflare blocked this request. Use an allowed runner/IP "
                    "or configure FLIGHTSFROM_PROXY; browser impersonation alone "
                    "cannot solve a JavaScript challenge."
                )
            response.raise_for_status()
            return parse(response)
        except (requests.RequestsError, ValueError) as error:
            if attempt == 3:
                raise RuntimeError(
                    f"Failed to fetch {url} after {attempt} attempts: {error}"
                ) from error
            print(f"! {url}: {error}; retrying in {attempt * 5}s...", flush=True)
            time.sleep(attempt * 5)


def parse_airports(response):
    data = response.json()
    if not isinstance(data, dict) or not data.get("response", {}).get("airports"):
        raise ValueError("Response did not contain a nonempty airport list")
    return data


def parse_metadata(response):
    data = response.json()
    metadata = data.get("response") if isinstance(data, dict) else None
    if (not isinstance(metadata, dict)
            or not isinstance(metadata.get("airport"), dict)
            or not metadata["airport"].get("IATA")
            or not isinstance(metadata.get("routes"), list)):
        raise ValueError("Response did not contain airport and routes metadata")
    return metadata


def main():
    session = requests.Session(
        impersonate="chrome", proxy=os.environ.get("FLIGHTSFROM_PROXY") or None,
        headers={
            "Accept": "application/json",
            "Origin": "https://www.flightsfrom.com",
            "Referer": "https://www.flightsfrom.com/",
        },
    )
    print("Fetching airports list...")
    airports_json = fetch(session, "https://www.flightsfrom.com/airports", parse_airports)

    iatas = [airport["IATA"] for airport in airports_json["response"]["airports"]]

    airports = defaultdict(dict)

    while iatas:
        iata = iatas.pop()
        if iata in airports:
            continue

        print("Fetching #%s: %s" % (len(airports), iata))

        metadata = fetch(
            session,
            "https://www.flightsfrom.com/api/airport/%s?from=%s" % (iata, iata),
            parse_metadata,
            allow_not_found=True,
        )
        if metadata is None:
            print("! Airport %s not found (404), skipping" % iata)
            continue


        airport_fields = [
            "city_name",
            "continent",
            "country",
            "country_code",
            "display_name",
            "elevation",
            "IATA",
            "ICAO",
            "latitude",
            "longitude",
            "name",
            "timezone",
        ]
        airport = {
            field.lower(): metadata["airport"][field] for field in airport_fields
        }
        if airport["latitude"] is not None:
            airport["latitude"] = clean_coord_str(airport["latitude"])
        if airport["longitude"] is not None:
            airport["longitude"] = clean_coord_str(airport["longitude"])
        if airport["elevation"]:
            airport["elevation"] = int(airport["elevation"])

        routes = []
        for route in metadata["routes"]:
            carrier_fields = [
                "name",
                "IATA",
            ]

            carriers = []
            for aroute in route["airlineroutes"]:
                is_passenger = (
                    str(aroute["airline"]["is_scheduled_passenger"]) == "1"
                    or str(aroute["airline"]["is_nonscheduled_passenger"]) == "1"
                )
                is_active = str(aroute["airline"]["active"]) == "1"
                if is_active and is_passenger:
                    carriers.append(
                        {
                            field.lower(): aroute["airline"][field]
                            for field in carrier_fields
                        }
                    )

            orig_ll = (
                float(airport["latitude"] or 0),
                float(airport["longitude"] or 0),
            )
            dest_ll = (
                float(clean_coord_str(route["airport"].get("latitude"))),
                float(clean_coord_str(route["airport"].get("longitude"))),
            )
            distance = int(geodesic(orig_ll, dest_ll).km)

            operating_days = [
                i for i in range(1, 8) if route.get(f"day{i}") == "yes"
            ]

            routes.append(
                {
                    "carriers": carriers,
                    "flights_per_week": int(route.get("flights_per_week") or 0),
                    "km": distance,
                    "min": int(route["common_duration"]),
                    "iata": route["iata_to"],
                    "operating_days": operating_days,
                }
            )

            iatas.append(route["iata_to"])

        airport["routes"] = routes
        airports[iata] = airport

        time.sleep(1)

    with open("airline_routes.json", "w") as f:
        f.write(json.dumps(airports, indent=4, sort_keys=True, separators=(",", ": ")))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
