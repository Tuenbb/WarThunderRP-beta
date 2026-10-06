from map_image import read_map_image_hash
from map_catalog import find_map_name

def main() -> None:
    try:
        fingerprint, dimensions = read_map_image_hash()
    except (OSError, TimeoutError, ValueError) as error:
        print(f"Nie można odczytać map.img ({type(error).__name__})")
        return

    print(f"Rozmiar obrazu: {dimensions[0]} × {dimensions[1]}")
    print(f"Odcisk obrazu: {fingerprint}")
    try:
        map_name = find_map_name(fingerprint)
    except (OSError, ValueError) as error:
        print(f"Nie można odczytać katalogu map ({type(error).__name__})")
        return

    print("Rozpoznana mapa:", map_name or "Nieznana mapa")

if __name__ == "__main__":
    main()
    