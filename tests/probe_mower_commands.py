#!/usr/bin/env python3
"""Manual probe: send mower commands to the live Gardena API and print the raw responses.

Not a pytest test (deliberately not named test_*). Requires env vars
GARDENA_CLIENT_ID, GARDENA_CLIENT_SECRET and GARDENA_MOWER_SERVICE_ID
(the MOWER service id, e.g. from tests/smoke_test_api.py output).
Useful when verifying which MOWER_CONTROL command names the API accepts.
"""

import asyncio
import json
import os
import aiohttp

CLIENT_ID = os.environ["GARDENA_CLIENT_ID"]
CLIENT_SECRET = os.environ["GARDENA_CLIENT_SECRET"]

AUTH_URL = "https://api.authentication.husqvarnagroup.dev/v1/oauth2/token"
COMMAND_URL = "https://api.smart.gardena.dev/v1/command"

MOWER_SERVICE_ID = os.environ["GARDENA_MOWER_SERVICE_ID"]


async def get_token(session):
    async with session.post(AUTH_URL, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }) as resp:
        result = await resp.json()
        return result["access_token"]


async def try_command(session, token, label, payload):
    url = f"{COMMAND_URL}/{MOWER_SERVICE_ID}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Api-Key": CLIENT_ID,
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }
    print(f"\n--- {label} ---")
    print(f"    payload: {json.dumps(payload)}")
    data = json.dumps(payload).encode("utf-8")
    async with session.put(url, headers=headers, data=data) as resp:
        body = await resp.text()
        print(f"    HTTP {resp.status}")
        if body:
            print(f"    response: {body[:300]}")


async def main():
    async with aiohttp.ClientSession() as session:
        token = await get_token(session)
        print(f"Token: {token[:20]}...")

        await try_command(session, token, "RESUME_SCHEDULE", {
            "data": {"type": "MOWER_CONTROL", "id": "req-1",
                     "attributes": {"command": "RESUME_SCHEDULE"}}
        })

        await try_command(session, token, "START_SECONDS_TO_OVERRIDE (3600s)", {
            "data": {"type": "MOWER_CONTROL", "id": "req-2",
                     "attributes": {"command": "START_SECONDS_TO_OVERRIDE", "seconds": 3600}}
        })

        await try_command(session, token, "PARK_UNTIL_NEXT_TASK (referens)", {
            "data": {"type": "MOWER_CONTROL", "id": "req-3",
                     "attributes": {"command": "PARK_UNTIL_NEXT_TASK"}}
        })

        await try_command(session, token, "PARK_UNTIL_FURTHER_NOTICE", {
            "data": {"type": "MOWER_CONTROL", "id": "req-4",
                     "attributes": {"command": "PARK_UNTIL_FURTHER_NOTICE"}}
        })


asyncio.run(main())
