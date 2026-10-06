import logging

from pypresence import Presence

logger = logging.getLogger(__name__)


class DiscordRpcClient:
    def __init__(self) -> None:
        self._client: Presence | None = None
        self.connected = False

    def _publish(
        self,
        state: str,
        *,
        large_image: str | None,
        large_text: str | None,
        small_image: str | None,
    ) -> None:
        if self._client is None:
            raise RuntimeError("Discord RPC client is not connected")

        details = "Gra w War Thunder"
        state_text = state[:128]

        if large_image and large_text and small_image:
            self._client.update(
                details=details,
                state=state_text,
                large_image=large_image,
                large_text=large_text,
                small_image=small_image,
            )
        elif large_image and large_text:
            self._client.update(
                details=details,
                state=state_text,
                large_image=large_image,
                large_text=large_text,
            )
        elif large_image and small_image:
            self._client.update(
                details=details,
                state=state_text,
                large_image=large_image,
                small_image=small_image,
            )
        elif large_image:
            self._client.update(
                details=details,
                state=state_text,
                large_image=large_image,
            )
        elif small_image:
            self._client.update(
                details=details,
                state=state_text,
                small_image=small_image,
            )
        else:
            self._client.update(
                details=details,
                state=state_text,
            )

    def update(
        self,
        client_id: str,
        state: str,
        *,
        vehicle_asset_key: str | None = None,
        flag_asset_key: str | None = None,
        vehicle_name: str | None = None,
        vehicle_image_url: str | None = None,
    ) -> bool:
        if not client_id.isdigit():
            logger.error("Discord Application ID is not configured")
            return False

        try:
            if self._client is None:
                self._client = Presence(client_id)

            if not self.connected:
                self._client.connect()
                self.connected = True

            try:
                self._publish(
                    state,
                    large_image=vehicle_image_url or vehicle_asset_key,
                    large_text=vehicle_name,
                    small_image=flag_asset_key,
                )
            except Exception:
                if not vehicle_image_url or not vehicle_asset_key:
                    raise

                logger.info(
                    "Remote vehicle image rejected; using Discord asset fallback"
                )
                self._publish(
                    state,
                    large_image=vehicle_asset_key,
                    large_text=vehicle_name,
                    small_image=flag_asset_key,
                )

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