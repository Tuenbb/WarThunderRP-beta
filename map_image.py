from io import BytesIO
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from PIL import Image, UnidentifiedImageError


MAP_IMAGE_URL = "http://127.0.0.1:8111/map.img"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(
    ProxyHandler({}),
    NoRedirectHandler(),
)


def read_map_image_hash() -> tuple[str, tuple[int, int]]:
    request = Request(
        MAP_IMAGE_URL,
        headers={"Accept": "image/*"},
        method="GET",
    )

    with _OPENER.open(request, timeout=2) as response:
        image_bytes = response.read(MAX_IMAGE_BYTES + 1)

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Obraz mapy przekracza limit 8 MiB")

    try:
        image = Image.open(BytesIO(image_bytes))
        size = image.size

        if size[0] <= 0 or size[1] <= 0:
            raise ValueError("Obraz mapy ma nieprawidłowy rozmiar")
        if size[0] * size[1] > MAX_IMAGE_PIXELS:
            raise ValueError("Obraz mapy przekracza limit pikseli")

        image.load()
        grayscale = image.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("Lokalne API nie zwróciło poprawnego obrazu") from error

    pixels = grayscale.tobytes()
    average = sum(pixels) / len(pixels)

    fingerprint = 0
    for index, pixel in enumerate(pixels):
        if pixel >= average:
            fingerprint |= 1 << index

    return f"{fingerprint:016x}", size