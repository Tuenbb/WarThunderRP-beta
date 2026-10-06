import logging

from pypresence import Presence

logger = logging.getLogger(__name__)
INVISIBLE_STATE_PLACEHOLDER = "\u2800"


class DiscordRpcClient:
    def __init__(self) -> None:
        self._client: Presence | None = None
        self.connected = False
        self.last_update_warning: str | None = None
        self.last_image_result: str | None = None

    def _publish(
        self,
        state: str | None,
        *,
        details: str | None,
        large_image: str | None,
        large_text: str | None,
        small_image: str | None,
        small_text: str | None,
    ) -> None:
        if self._client is None:
            raise RuntimeError("Discord RPC client is not connected")

        payload: dict[str, str] = {}
        if details:
            payload["details"] = details[:128]
        if state:
            payload["state"] = state[:128]
        elif large_image or small_image:
            payload["state"] = INVISIBLE_STATE_PLACEHOLDER
        if large_image:
            payload["large_image"] = large_image
            if large_text:
                payload["large_text"] = large_text[:128]
        if small_image:
            payload["small_image"] = small_image
            if small_text:
                payload["small_text"] = small_text[:128]
        self._client.update(**payload)

    def update(
        self,
        client_id: str,
        state: str | None,
        *,
        details: str | None = None,
        vehicle_asset_key: str | None = None,
        flag_asset_key: str | None = None,
        flag_name: str | None = None,
        vehicle_name: str | None = None,
        vehicle_image_url: str | None = None,
    ) -> bool:
        if not client_id.isdigit():
            logger.error("Discord Application ID is not configured")
            return False

        self.last_update_warning = None
        self.last_image_result = None
        try:
            if self._client is None:
                self._client = Presence(client_id)

            if not self.connected:
                self._client.connect()
                self.connected = True

            candidates = [
                (
                    vehicle_image_url or vehicle_asset_key,
                    vehicle_name,
                    flag_asset_key,
                    flag_name,
                ),
            ]
            if vehicle_image_url:
                candidates.extend(
                    [
                        (
                            vehicle_asset_key,
                            vehicle_name if vehicle_asset_key else None,
                            flag_asset_key,
                            flag_name,
                        ),
                        (vehicle_image_url, vehicle_name, None, None),
                    ]
                )
            if vehicle_asset_key:
                candidates.append(
                    (vehicle_asset_key, vehicle_name, None, None)
                )
            if flag_asset_key:
                candidates.append((None, None, flag_asset_key, flag_name))
            candidates.append((None, None, None, None))

            seen: set[tuple[str | None, str | None, str | None, str | None]] = set()
            last_error: Exception | None = None
            failed_attempts = 0
            for large_image, large_text, small_image, small_text in candidates:
                candidate = (large_image, large_text, small_image, small_text)
                if candidate in seen:
                    continue
                seen.add(candidate)
                try:
                    self._publish(
                        state,
                        details=details,
                        large_image=large_image,
                        large_text=large_text,
                        small_image=small_image,
                        small_text=small_text,
                    )
                    accepted_large = bool(large_image)
                    accepted_small = bool(small_image)
                    if accepted_large and accepted_small:
                        self.last_image_result = "vehicle+flag"
                    elif accepted_large:
                        self.last_image_result = "vehicle"
                    elif accepted_small:
                        self.last_image_result = "flag"
                    else:
                        self.last_image_result = "none"
                    if failed_attempts:
                        self.last_update_warning = (
                            f"częściowy fallback ({self.last_image_result})"
                            if accepted_large or accepted_small
                            else "Discord odrzucił obrazy"
                        )
                    break
                except Exception as error:
                    last_error = error
                    failed_attempts += 1
                    logger.info(
                        "Discord RPC rejected an image combination (%s)",
                        type(error).__name__,
                    )
            else:
                if last_error is not None:
                    raise last_error

            return True
        except Exception as error:
            print(
                f"Discord RPC update failed "
                f"({type(error).__name__}): {error}"
            )
            self.disconnect()
            return False

    def disconnect(self) -> None:
        client = self._client
        self._client = None
        self.connected = False

        if client is None:
            return

        try:
            client.clear()
        except Exception as error:
            logger.info("Could not clear Discord RPC (%s)", type(error).__name__)

        try:
            client.close()
        except Exception as error:
            logger.info("Could not close Discord RPC (%s)", type(error).__name__)