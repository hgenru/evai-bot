from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import httpx


class VtuberClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def list_sessions(self) -> List[str]:
        url = f"{self.base_url}/v1/sessions"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                raise ValueError("Unexpected sessions response")
            return [str(x) for x in data]

    async def speak(
        self,
        *,
        text: str,
        client_uid: Optional[str] = None,
        display_name: Optional[str] = None,
        avatar: Optional[str] = None,
        motions: Optional[Sequence[str]] = None,
        expressions: Optional[Sequence[Union[str, int]]] = None,
        extract_emotions: Optional[bool] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/direct-control/speak"
        payload: Dict[str, Any] = {"text": text}
        if client_uid:
            payload["client_uid"] = client_uid
        if display_name:
            payload["display_name"] = display_name
        if avatar:
            payload["avatar"] = avatar
        actions: Dict[str, Any] = {}
        if motions:
            actions["motions"] = list(motions)
        if expressions:
            actions["expressions"] = list(expressions)
        if actions:
            payload["actions"] = actions
        if extract_emotions is not None:
            payload["extract_emotions"] = extract_emotions

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def system_instruction(
        self,
        *,
        text: str,
        client_uid: Optional[str] = None,
        mode: str = "append",
        apply_to_all: Optional[bool] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/direct-control/system"
        payload: Dict[str, Any] = {"text": text, "mode": mode}
        if client_uid:
            payload["client_uid"] = client_uid
        if apply_to_all is not None:
            payload["apply_to_all"] = apply_to_all
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def agent_say(
        self,
        *,
        text: str,
        client_uid: Optional[str] = None,
        apply_to_all: Optional[bool] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/direct-control/agent-say"
        payload: Dict[str, Any] = {"text": text}
        if client_uid:
            payload["client_uid"] = client_uid
        if apply_to_all is not None:
            payload["apply_to_all"] = apply_to_all
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
